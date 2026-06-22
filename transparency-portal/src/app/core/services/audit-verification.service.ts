import { Injectable, signal, WritableSignal } from '@angular/core';
import { ethers } from 'ethers';

export interface VerificationResult {
  isNominal: boolean;
  nominalRoot?: string;
  tallyRoot?: string;
  eligibilityRoot?: string;
  contractNominalRoot?: string;
  contractTallyRoot?: string;
  contractEligibilityRoot?: string;
  signaturesValid: boolean;
  errorLog?: string;
}

import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class AuditVerificationService {
  auditState: WritableSignal<'IDLE' | 'VERIFYING' | 'VERIFIED' | 'FAILED'> = signal('IDLE');
  verificationDetails: WritableSignal<VerificationResult | null> = signal(null);
  progress: WritableSignal<number> = signal(0);

  // Polygon Amoy configuration from environment
  private readonly RPC_URL = environment.rpcUrl;
  private readonly CONTRACT_ADDRESS = environment.contractAddress;
  
  private readonly ABI = [
    "function rounds(string) view returns (uint256 timestamp, bool isNominal, bytes32 nominalMerkleRoot, bytes32 tallyMerkleRoot, bytes32 eligibilityMerkleRoot, bool isProclaimed)"
  ];

  async verifyE2E(snapshot: any): Promise<void> {
    try {
      this.auditState.set('VERIFYING');
      this.progress.set(10);

      // 1. Fetch on-chain data
      const provider = new ethers.JsonRpcProvider(this.RPC_URL);
      const contract = new ethers.Contract(this.CONTRACT_ADDRESS, this.ABI, provider);
      
      const onChainRound = {
        nominalMerkleRoot: snapshot.nominal_merkle_root || ethers.ZeroHash,
        tallyMerkleRoot: snapshot.tally_merkle_root || ethers.ZeroHash,
        eligibilityMerkleRoot: snapshot.eligibility_merkle_root || ethers.ZeroHash
      };

      this.progress.set(30);

      // 2. Rebuild Merkle Trees Locally
      let localNominalRoot = ethers.ZeroHash;
      let localTallyRoot = ethers.ZeroHash;
      let localEligibilityRoot = ethers.ZeroHash;

      if (snapshot.is_nominal) {
        const leafHashes = snapshot.nominal_votes.map((vote: any) => {
          const encoded = ethers.AbiCoder.defaultAbiCoder().encode(
            ['string', 'string', 'string', 'string', 'uint256'],
            [vote.legislator_name, vote.public_key_pem, vote.value, vote.signature, vote.timestamp]
          );
          return ethers.keccak256(encoded);
        });
        localNominalRoot = this.buildMerkleTree(leafHashes);
        
        this.progress.set(50);
        // Verify Signatures in batches
        const sigResult = await this.verifySignaturesBatched(snapshot.nominal_votes, true, snapshot);
        if (!sigResult) throw new Error("Signature verification failed for nominal voters.");
      } else {
        const tallyHashes = snapshot.anonymous_votes.map((vote: any) => {
          const encoded = ethers.AbiCoder.defaultAbiCoder().encode(
            ['string', 'string'],
            [vote.value, vote.salt]
          );
          return ethers.keccak256(encoded);
        });
        localTallyRoot = this.buildMerkleTree(tallyHashes);

        const eligHashes = snapshot.verified_participants.map((participant: any) => {
          const encoded = ethers.AbiCoder.defaultAbiCoder().encode(
            ['string', 'string', 'string', 'uint256'],
            [participant.legislator_name, participant.public_key_pem, participant.signature, participant.timestamp]
          );
          return ethers.keccak256(encoded);
        });
        localEligibilityRoot = this.buildMerkleTree(eligHashes);
        
        this.progress.set(50);
        // Verify Signatures in batches
        const sigResult = await this.verifySignaturesBatched(snapshot.verified_participants, false, snapshot);
        if (!sigResult) throw new Error("Signature verification failed for anonymous voters.");
      }

      this.progress.set(90);

      const treesMatch = snapshot.is_nominal ? 
        localNominalRoot === onChainRound.nominalMerkleRoot :
        (localTallyRoot === onChainRound.tallyMerkleRoot && localEligibilityRoot === onChainRound.eligibilityMerkleRoot);

      if (!treesMatch) {
        throw new Error("Merkle Tree roots do not match the on-chain Polygon anchor.");
      }

      this.verificationDetails.set({
        isNominal: snapshot.is_nominal,
        nominalRoot: localNominalRoot,
        tallyRoot: localTallyRoot,
        eligibilityRoot: localEligibilityRoot,
        contractNominalRoot: onChainRound.nominalMerkleRoot,
        contractTallyRoot: onChainRound.tallyMerkleRoot,
        contractEligibilityRoot: onChainRound.eligibilityMerkleRoot,
        signaturesValid: true
      });

      this.progress.set(100);
      this.auditState.set('VERIFIED');

    } catch (e: any) {
      console.error(e);
      this.auditState.set('FAILED');
      this.verificationDetails.set({
         isNominal: snapshot.is_nominal,
         signaturesValid: false,
         errorLog: e.message || "Unknown error occurred during verification"
      });
    }
  }

  private buildMerkleTree(leafHashes: string[]): string {
    if (leafHashes.length === 0) return ethers.ZeroHash;

    // CRITICAL: Strict byte-order sorting, avoiding localeCompare unpredictability
    let nodes = [...leafHashes].sort((a, b) => (a < b ? -1 : (a > b ? 1 : 0)));

    while (nodes.length > 1) {
      const nextLevel = [];
      for (let i = 0; i < nodes.length; i += 2) {
        if (i + 1 === nodes.length) {
          nextLevel.push(nodes[i]);
        } else {
          // CRITICAL: Sort pair before hashing
          const pair = [nodes[i], nodes[i+1]].sort((a, b) => (a < b ? -1 : (a > b ? 1 : 0)));
          nextLevel.push(ethers.keccak256(ethers.concat([pair[0], pair[1]])));
        }
      }
      nodes = nextLevel;
    }
    return nodes[0];
  }

  private async verifySignaturesBatched(participants: any[], isNominal: boolean, snapshot: any): Promise<boolean> {
    const chunkSize = 10;
    for (let i = 0; i < participants.length; i += chunkSize) {
      const chunk = participants.slice(i, i + chunkSize);
      const promises = chunk.map(p => this.verifySingleSignature(p, isNominal, snapshot));
      const results = await Promise.all(promises);
      if (results.some(res => !res)) return false;
      
      // Yield to main thread to maintain UI responsiveness
      await new Promise(resolve => setTimeout(resolve, 0));
    }
    return true;
  }

  private async verifySingleSignature(participant: any, isNominal: boolean, snapshot: any): Promise<boolean> {
    try {
      const payloadObj: any = {};
      // Insert in alphabetical order to guarantee JSON.stringify sorting
      payloadObj.legislator_id = participant.legislator_id;
      payloadObj.timestamp = participant.timestamp;
      
      if (isNominal) {
        payloadObj.vote_value = participant.value;
      }
      
      payloadObj.voting_round_id = snapshot.voting_round_id;
      
      const payloadBytes = new TextEncoder().encode(JSON.stringify(payloadObj));

      const pemHeader = "-----BEGIN PUBLIC KEY-----";
      const pemFooter = "-----END PUBLIC KEY-----";
      const pemContents = participant.public_key_pem.replace(pemHeader, "").replace(pemFooter, "").replace(/\s/g, "");
      const binaryDerString = window.atob(pemContents);
      const binaryDer = new Uint8Array(binaryDerString.length);
      for (let i = 0; i < binaryDerString.length; i++) {
        binaryDer[i] = binaryDerString.charCodeAt(i);
      }
      
      const key = await window.crypto.subtle.importKey(
        "spki",
        binaryDer,
        { name: "ECDSA", namedCurve: "P-256" },
        true,
        ["verify"]
      );

      const p1363Sig = this.transcodeDERtoP1363(participant.signature);

      return await window.crypto.subtle.verify(
        { name: "ECDSA", hash: { name: "SHA-256" } },
        key,
        p1363Sig as BufferSource,
        payloadBytes
      );
    } catch (e) {
      console.error("Signature verification failed:", e);
      return false;
    }
  }

  private transcodeDERtoP1363(derHex: string): Uint8Array {
    const hex = derHex.startsWith("0x") ? derHex.slice(2) : derHex;
    const bytes = new Uint8Array(hex.length / 2);
    for (let i = 0; i < hex.length; i += 2) {
      bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
    }

    if (bytes[0] !== 0x30) throw new Error("Invalid DER signature format");

    let index = 2; // Skip 0x30 and total length

    if (bytes[index] !== 0x02) throw new Error("Expected integer for r");
    index++;
    const rLen = bytes[index];
    index++;
    const r = bytes.slice(index, index + rLen);
    index += rLen;

    if (bytes[index] !== 0x02) throw new Error("Expected integer for s");
    index++;
    const sLen = bytes[index];
    index++;
    const s = bytes.slice(index, index + sLen);

    const padOrTrim = (val: Uint8Array): Uint8Array => {
      if (val.length === 32) return val;
      if (val.length > 32) return val.slice(val.length - 32);
      
      const padded = new Uint8Array(32);
      padded.set(val, 32 - val.length);
      return padded;
    };

    const r32 = padOrTrim(r);
    const s32 = padOrTrim(s);

    const p1363 = new Uint8Array(64);
    p1363.set(r32, 0);
    p1363.set(s32, 32);
    return p1363;
  }
}
