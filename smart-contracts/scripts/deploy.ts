import { ethers } from "hardhat";
import * as fs from "fs";
import * as path from "path";

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying contracts with the account:", deployer.address);

  const Notary = await ethers.getContractFactory("LegislativeNotary");
  const notary = await Notary.deploy();

  await notary.waitForDeployment();
  const address = await notary.getAddress();

  console.log("LegislativeNotary deployed to:", address);

  // Export ABI and Address for the Python Backend and Angular Frontend
  const exportDir = path.join(__dirname, "../exports/abi");
  if (!fs.existsSync(exportDir)) {
    fs.mkdirSync(exportDir, { recursive: true });
  }

  // Get the artifact (which contains the ABI)
  const artifactPath = path.join(
    __dirname,
    "../artifacts/contracts/LegislativeNotary.sol/LegislativeNotary.json"
  );
  
  if (fs.existsSync(artifactPath)) {
    const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf8"));
    const exportData = {
      address: address,
      abi: artifact.abi,
    };
    
    const exportPath = path.join(exportDir, "LegislativeNotary.json");
    fs.writeFileSync(exportPath, JSON.stringify(exportData, null, 2));
    console.log(`ABI exported to ${exportPath}`);
  } else {
    console.error("Artifact not found. Make sure to compile first.");
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
