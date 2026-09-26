import { readFile, readdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const outputRoot = fileURLToPath(new URL('../dist/', import.meta.url));
const forbidden = [
  'contract-placeholder',
  'Bearer contract-',
  'clothes_admin_session',
  '.env.local',
  'super-secret-value',
];

async function filesUnder(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const path = join(directory, entry.name);
    files.push(...(entry.isDirectory() ? await filesUnder(path) : [path]));
  }
  return files;
}

for (const file of await filesUnder(outputRoot)) {
  const content = await readFile(file, 'utf8');
  for (const token of forbidden) {
    if (content.includes(token)) {
      throw new Error(`Production bundle contains forbidden token ${JSON.stringify(token)} in ${file}.`);
    }
  }
}

console.log('Production bundle credential scan passed.');
