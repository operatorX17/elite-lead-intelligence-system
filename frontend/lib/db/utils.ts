import { generateId } from "ai";
import { genSaltSync, hashSync } from "bcrypt-ts";

export function generateHashedPassword(password: string) {
  const salt = genSaltSync(10);
  const hash = hashSync(password, salt);

  return hash;
}

const PLACEHOLDER_PASSWORD_HASH = generateHashedPassword(generateId());

export function generateDummyPassword() {
  return PLACEHOLDER_PASSWORD_HASH;
}

export function generatePlaceholderPasswordHash() {
  return PLACEHOLDER_PASSWORD_HASH;
}
