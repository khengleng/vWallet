// SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;

contract AnchorRegistry {
    event Anchored(bytes32 indexed hash, address indexed sender, uint256 timestamp);

    function anchor(bytes32 hash) external {
        emit Anchored(hash, msg.sender, block.timestamp);
    }
}
