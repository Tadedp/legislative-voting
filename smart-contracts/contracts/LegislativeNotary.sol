// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title LegislativeNotary
 * @dev Anchors Merkle Roots for the Legislative Electronic Voting System.
 * Implements Gas Optimized Data Packing.
 */
contract LegislativeNotary {
    address public immutable orchestratorAdmin;

    struct VotingRound {
        bytes32 nominalMerkleRoot;
        bytes32 tallyMerkleRoot;
        bytes32 eligibilityMerkleRoot;
        uint64 timestamp;
        bool isNominal;
        bool isProclaimed;
    }

    mapping(string => VotingRound) public rounds;

    // Notice string roundId does NOT have 'indexed' to avoid hashing in topics.
    // This allows the frontend to natively decode the UUID string.
    event RoundProclaimed(
        string roundId, 
        bool isNominal,
        bytes32 nominalRoot,
        bytes32 tallyRoot, 
        bytes32 eligibilityRoot, 
        string agendaItemTitle, 
        uint256 timestamp
    );

    error Unauthorized();
    error AlreadyProclaimed();

    constructor() {
        orchestratorAdmin = msg.sender;
    }

    modifier onlyAdmin() {
        if (msg.sender != orchestratorAdmin) revert Unauthorized();
        _;
    }

    function proclaimRound(
        string calldata _roundId, 
        string calldata _title, 
        bool _isNominal,
        bytes32 _nominalRoot,
        bytes32 _tallyRoot,
        bytes32 _eligibilityRoot
    ) external onlyAdmin {
        if (rounds[_roundId].isProclaimed) revert AlreadyProclaimed();

        rounds[_roundId] = VotingRound({
            nominalMerkleRoot: _nominalRoot,
            tallyMerkleRoot: _tallyRoot,
            eligibilityMerkleRoot: _eligibilityRoot,
            timestamp: uint64(block.timestamp),
            isNominal: _isNominal,
            isProclaimed: true
        });

        emit RoundProclaimed(
            _roundId, 
            _isNominal, 
            _nominalRoot, 
            _tallyRoot, 
            _eligibilityRoot, 
            _title, 
            block.timestamp
        );
    }
}
