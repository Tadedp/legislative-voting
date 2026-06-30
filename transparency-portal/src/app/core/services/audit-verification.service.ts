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
  eligibilityCount?: number;
  tallyCount?: number;
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
    "function rounds(string) view returns (bytes32 nominalMerkleRoot, bytes32 tallyMerkleRoot, bytes32 eligibilityMerkleRoot, uint64 timestamp, bool isNominal, bool isProclaimed)"
  ];

  async verifyE2E(snapshot: any): Promise<void> {
    try {
      this.auditState.set('VERIFYING');
      this.progress.set(10);

      // 1. Fetch on-chain data
      const provider = new ethers.JsonRpcProvider(this.RPC_URL);
      const contract = new ethers.Contract(this.CONTRACT_ADDRESS, this.ABI, provider);
      
      const roundData = await contract['rounds'](snapshot.voting_round_id);
      
      if (!roundData.isProclaimed) {
        throw new Error("This voting round has not been notarized on the blockchain.");
      }

      if (snapshot.is_nominal !== roundData.isNominal) {
        throw new Error("Round type mismatch between on-chain data and local snapshot.");
      }

      const onChainRound = {
        nominalMerkleRoot: roundData.nominalMerkleRoot || ethers.ZeroHash,
        tallyMerkleRoot: roundData.tallyMerkleRoot || ethers.ZeroHash,
        eligibilityMerkleRoot: roundData.eligibilityMerkleRoot || ethers.ZeroHash
      };

      this.progress.set(30);

      // 2. Rebuild Merkle Trees Locally
      let localNominalRoot = ethers.ZeroHash;
      let localTallyRoot = ethers.ZeroHash;
      let localEligibilityRoot = ethers.ZeroHash;

      if (snapshot.is_nominal) {
        const leafHashes = snapshot.nominal_votes.map((vote: any) => {
          const encoded = ethers.AbiCoder.defaultAbiCoder().encode(
            ['string', 'string', 'string', 'string', 'string', 'uint256'],
            [snapshot.voting_round_id, vote.legislator_name, vote.public_key_pem, vote.value, vote.signature, vote.timestamp]
          );
          return ethers.keccak256(ethers.concat(["0x00", encoded]));
        });
        
        if (snapshot.tie_breaker_vote) {
            const tb = snapshot.tie_breaker_vote;
            const tbEncoded = ethers.AbiCoder.defaultAbiCoder().encode(
                ['string', 'string', 'string', 'string', 'string', 'uint256'],
                ["TIE_BREAKER", snapshot.voting_round_id, tb.legislator_id, tb.value, tb.signature, tb.timestamp]
            );
            leafHashes.push(ethers.keccak256(ethers.concat(["0x00", tbEncoded])));
        }
        
        localNominalRoot = this.buildMerkleTree(leafHashes);
        
        this.progress.set(50);
        // Verify Signatures in batches
        const sigResult = await this.verifySignaturesBatched(snapshot.nominal_votes, true, snapshot);
        if (!sigResult) throw new Error("Signature verification failed for nominal voters.");
        
        if (snapshot.tie_breaker_vote) {
            const tbResult = await this.verifySingleSignature(snapshot.tie_breaker_vote, true, snapshot);
            if (!tbResult) throw new Error("Signature verification failed for tie-breaker vote.");
        }
      } else {
        const tallyHashes = snapshot.anonymous_votes.map((vote: any) => {
          vote.ephemeralHash = ethers.sha256(ethers.getBytes("0x" + vote.ephemeral_pub)).replace("0x", "");
          const encoded = ethers.AbiCoder.defaultAbiCoder().encode(
            ['string', 'string', 'string', 'string', 'string'],
            [snapshot.voting_round_id, vote.value, vote.ephemeral_pub, vote.server_signature, vote.vote_signature]
          );
          return ethers.keccak256(ethers.concat(["0x00", encoded]));
        });
        
        if (snapshot.tie_breaker_vote) {
            const tb = snapshot.tie_breaker_vote;
            const tbEncoded = ethers.AbiCoder.defaultAbiCoder().encode(
                ['string', 'string', 'string', 'string', 'string', 'uint256'],
                ["TIE_BREAKER", snapshot.voting_round_id, tb.legislator_id, tb.value, tb.signature, tb.timestamp]
            );
            tallyHashes.push(ethers.keccak256(ethers.concat(["0x00", tbEncoded])));
        }
        localTallyRoot = this.buildMerkleTree(tallyHashes);

        const eligHashes = snapshot.verified_participants.map((participant: any) => {
          const encoded = ethers.AbiCoder.defaultAbiCoder().encode(
            ['string', 'string', 'string', 'string', 'string', 'string', 'uint256'],
            ["ELIGIBILITY", snapshot.voting_round_id, participant.legislator_name, participant.public_key_pem, participant.blinded_token, participant.signature, participant.timestamp]
          );
          return ethers.keccak256(ethers.concat(["0x00", encoded]));
        });
        localEligibilityRoot = this.buildMerkleTree(eligHashes);
        
        this.progress.set(50);
        // Verify Phase 1 Auth Signatures
        const sigResult = await this.verifySignaturesBatched(snapshot.verified_participants, false, snapshot);
        if (!sigResult) throw new Error("Signature verification failed for anonymous voters.");
        
        // Verify Phase 2 Anonymous Signatures
        const anonSigResult = await this.verifyAnonymousVotesBatched(snapshot.anonymous_votes, snapshot);
        if (!anonSigResult) throw new Error("Zero-Trust blind signature verification failed for anonymous votes.");

        if (snapshot.tie_breaker_vote) {
            const tbResult = await this.verifySingleSignature(snapshot.tie_breaker_vote, true, snapshot);
            if (!tbResult) throw new Error("Signature verification failed for tie-breaker vote.");
        }
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
        signaturesValid: true,
        eligibilityCount: snapshot.verified_participants?.length || 0,
        tallyCount: snapshot.anonymous_votes?.length || 0,
      });

      this.progress.set(100);
      this.auditState.set('VERIFIED');

    } catch (e: any) {
      console.error(e);
      this.auditState.set('FAILED');
      this.verificationDetails.set({
         isNominal: snapshot?.is_nominal,
         signaturesValid: false,
         errorLog: e.message || "Unknown error occurred during verification"
      });
    }
  }

  private buildMerkleTree(leafHashes: string[]): string {
    if (leafHashes.length === 0) return ethers.ZeroHash;

    let nodes = [...leafHashes].sort((a, b) => (a < b ? -1 : (a > b ? 1 : 0)));

    while (nodes.length > 1) {
      const nextLevel = [];
      for (let i = 0; i < nodes.length; i += 2) {
        if (i + 1 === nodes.length) {
          const pair = [nodes[i], nodes[i]];
          nextLevel.push(ethers.keccak256(ethers.concat(["0x01", pair[0], pair[1]])));
        } else {
          const pair = [nodes[i], nodes[i+1]].sort((a, b) => (a < b ? -1 : (a > b ? 1 : 0)));
          nextLevel.push(ethers.keccak256(ethers.concat(["0x01", pair[0], pair[1]])));
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
      await new Promise(resolve => setTimeout(resolve, 0));
    }
    return true;
  }

  private pemToArrayBuffer(pem: string): ArrayBuffer {
    const pemContents = pem.replace(/-----BEGIN [A-Z ]+-----/, "").replace(/-----END [A-Z ]+-----/, "").replace(/\s/g, "");
    const binaryStr = window.atob(pemContents);
    const bytes = new Uint8Array(binaryStr.length);
    for (let i = 0; i < binaryStr.length; i++) {
      bytes[i] = binaryStr.charCodeAt(i);
    }
    return bytes.buffer;
  }

  private async verifySingleSignature(participant: any, isNominal: boolean, snapshot: any): Promise<boolean> {
    try {
      let payloadBytes: Uint8Array;

      if (isNominal) {
        const payloadObj: any = {};
        payloadObj.legislator_id = participant.legislator_id;
        payloadObj.timestamp = participant.timestamp;
        payloadObj.vote_value = participant.value;
        payloadObj.voting_round_id = snapshot.voting_round_id;
        payloadBytes = new TextEncoder().encode(JSON.stringify(payloadObj));
      } else {
        // For phase 1 verified_participants, payload is the raw hex bytes of blinded_token
        payloadBytes = ethers.getBytes("0x" + participant.blinded_token) as Uint8Array;
      }
      
      const keyBuffer = this.pemToArrayBuffer(participant.public_key_pem);
      const key = await window.crypto.subtle.importKey(
        "spki",
        keyBuffer,
        { name: "ECDSA", namedCurve: "P-256" },
        true,
        ["verify"]
      );

      const p1363Sig = this.transcodeDERtoP1363(participant.signature);

      return await window.crypto.subtle.verify(
        { name: "ECDSA", hash: { name: "SHA-256" } },
        key,
        p1363Sig as BufferSource,
        payloadBytes as BufferSource
      );
    } catch (e) {
      console.error("Signature verification failed:", e);
      return false;
    }
  }

  private async verifyAnonymousVotesBatched(anonymousVotes: any[], snapshot: any): Promise<boolean> {
    if (!snapshot.ephemeral_public_key) throw new Error("Missing server ephemeral public key.");

    const serverRsaKey = await window.crypto.subtle.importKey(
      "spki",
      this.pemToArrayBuffer(snapshot.ephemeral_public_key),
      { name: "RSA-PSS", hash: "SHA-256" },
      true,
      ["verify"]
    );

    const chunkSize = 10;
    for (let i = 0; i < anonymousVotes.length; i += chunkSize) {
      const chunk = anonymousVotes.slice(i, i + chunkSize);
      const promises = chunk.map(vote => this.verifyAnonymousVote(vote, serverRsaKey));
      const results = await Promise.all(promises);
      if (results.some(res => !res)) return false;
      await new Promise(resolve => setTimeout(resolve, 0));
    }
    return true;
  }

  private async verifyAnonymousVote(vote: any, serverRsaKey: CryptoKey): Promise<boolean> {
    try {
      // 1. Verify server_signature (RSA-PSS) against SHA256(ephemeral_pub)
      const ephemeralPubBytes = ethers.getBytes("0x" + vote.ephemeral_pub) as Uint8Array;
      const ephemeralHash = await window.crypto.subtle.digest("SHA-256", ephemeralPubBytes as BufferSource);

      const serverSigBytes = ethers.getBytes("0x" + vote.server_signature) as Uint8Array;
      const isServerValid = await window.crypto.subtle.verify(
        { name: "RSA-PSS", saltLength: 32 },
        serverRsaKey,
        serverSigBytes as BufferSource,
        ephemeralHash as BufferSource
      );
      if (!isServerValid) {
        console.error("Server signature invalid for vote:", vote.ephemeral_pub);
        return false;
      }

      // 2. Verify vote_signature (ECDSA) against vote_value
      const voteValueBytes = new TextEncoder().encode(vote.value);
      const ecdsaKeyBytes = ethers.getBytes("0x" + vote.ephemeral_pub) as Uint8Array;
      const voterKey = await window.crypto.subtle.importKey(
        "raw",
        ecdsaKeyBytes as BufferSource,
        { name: "ECDSA", namedCurve: "P-256" },
        true,
        ["verify"]
      );

      const p1363Sig = this.transcodeDERtoP1363(vote.vote_signature);
      const isVoteValid = await window.crypto.subtle.verify(
        { name: "ECDSA", hash: { name: "SHA-256" } },
        voterKey,
        p1363Sig as BufferSource,
        voteValueBytes as BufferSource
      );
      if (!isVoteValid) {
        console.error("Vote signature invalid for vote:", vote.ephemeral_pub);
        return false;
      }

      return true;
    } catch (e) {
      console.error("Anonymous vote verification failed:", e);
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
