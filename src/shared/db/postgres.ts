import {
  Pool,
  type PoolClient,
  type QueryResult,
  type QueryResultRow,
} from "pg";

import { env } from "../config/env.js";
import { createLogger } from "../logging/logger.js";

const logger = createLogger("shared:postgres");

let pool: Pool | null = null;

export interface DatabaseExecutor {
  query<T extends QueryResultRow>(
    text: string,
    values?: unknown[],
  ): Promise<QueryResult<T>>;
}

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

export async function withTransaction<T>(
  callback: (client: PoolClient) => Promise<T>,
) {
  const client = await getPool().connect();

  try {
    await client.query("BEGIN");
    const result = await callback(client);
    await client.query("COMMIT");
    return result;
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
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
