import { Pool, type QueryResult, type QueryResultRow } from "pg";

import { env } from "../config/env.js";
import { createLogger } from "../logging/logger.js";

const logger = createLogger("shared:postgres");

let pool: Pool | null = null;

function getPool() {
  if (!pool) {
    pool = new Pool({
      connectionString: env.databaseUrl,
    });

    pool.on("error", (error: Error) => {
      logger.error("Unexpected PostgreSQL pool error", { error });
    });
  }

  return pool;
}

export async function query<T extends QueryResultRow>(
  text: string,
  values?: unknown[],
): Promise<QueryResult<T>> {
  return getPool().query<T>(text, values);
}

export async function assertDatabaseConnection() {
  await query("SELECT 1");
  logger.info("PostgreSQL connection ready");
}

export async function closeDatabaseConnection() {
  if (pool) {
    await pool.end();
    pool = null;
  }
}
