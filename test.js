import {
  S3Client,
  ListObjectsV2Command,
  GetObjectCommand,
} from "@aws-sdk/client-s3";

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

process.loadEnvFile();

const credentials = {
  accessKeyId: process.env.AWS_ACCESS_KEY_ID,
  secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
};

if (!credentials.accessKeyId || !credentials.secretAccessKey) {
  throw new Error(
    "Missing AWS credentials. Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env."
  );
}

const client = new S3Client({
  region: "ap-south-1",
  credentials,
});

const bucketName = "procurepumps";
const folderPath = "Pumps/";

/* ------------------------ BUILD TREE ------------------------ */

function addPathToTree(tree, key) {
  const relativePath = key.replace(folderPath, "");

  if (!relativePath) return;

  const parts = relativePath.split("/").filter(Boolean);

  let current = tree;

  parts.forEach((part, index) => {
    const isFile = index === parts.length - 1;

    if (!current[part]) {
      current[part] = isFile ? null : {};
    }

    if (!isFile) {
      current = current[part];
    }
  });
}

/* ------------------------ PRINT TREE ------------------------ */

function printTree(tree, prefix = "") {
  const entries = Object.entries(tree).sort(([a], [b]) => a.localeCompare(b));

  entries.forEach(([name, children]) => {
    console.log(prefix + name);

    if (children) {
      printTree(children, prefix + "    ");
    }
  });
}

/* ------------------------ LIST FILES ------------------------ */

async function getAllFiles() {
  const files = [];
  let continuationToken;

  do {
    const command = new ListObjectsV2Command({
      Bucket: bucketName,
      Prefix: folderPath,
      ContinuationToken: continuationToken,
    });

    const response = await client.send(command);

    if (response.Contents) {
      response.Contents.forEach((file) => {
        // Skip folder placeholders
        if (!file.Key || file.Key.endsWith("/")) return;

        files.push(file.Key);
      });
    }

    continuationToken = response.NextContinuationToken;
  } while (continuationToken);

  return files;
}

/* ------------------------ DOWNLOAD ------------------------ */

async function downloadFile(key) {
  console.log("Downloading:", key);

  const command = new GetObjectCommand({
    Bucket: bucketName,
    Key: key,
  });

  const response = await client.send(command);

  const bytes = await response.Body.transformToByteArray();

  await mkdir(path.dirname(key), { recursive: true });

  await writeFile(key, bytes);
}

/* ------------------------ MAIN ------------------------ */

async function listFiles() {
  try {
    const files = await getAllFiles();

    if (files.length === 0) {
      console.log("No files found.");
      return;
    }

    console.log(`${bucketName}/${folderPath}`);

    // Build tree ONLY for displaying
    const tree = {};

    files.forEach((key) => addPathToTree(tree, key));

    printTree(tree);

    console.log("\nDownloading files...\n");

    // Download using ORIGINAL S3 keys
    for (const key of files) {
      await downloadFile(key);
    }

    console.log("\nFinished downloading all files.");
  } catch (err) {
    console.error(err);
  }
}

listFiles();
