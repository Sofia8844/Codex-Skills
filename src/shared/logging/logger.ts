type LogLevel = "debug" | "info" | "warn" | "error";

function serializeError(error: unknown) {
  if (error instanceof Error) {
    return {
      name: error.name,
      message: error.message,
      stack: error.stack,
    };
  }

  return error;
}

function writeLog(
  level: LogLevel,
  scope: string,
  message: string,
  metadata?: Record<string, unknown>,
) {
  const payload = {
    timestamp: new Date().toISOString(),
    level,
    scope,
    message,
    ...(metadata ? { metadata } : {}),
  };

  const serialized = JSON.stringify(payload);

  if (level === "error") {
    console.error(serialized);
    return;
  }

  console.log(serialized);
}

export function getErrorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }

  if (typeof error === "string") {
    return error;
  }

  return "Unknown error";
}

export function createLogger(scope: string) {
  return {
    debug(message: string, metadata?: Record<string, unknown>) {
      writeLog("debug", scope, message, metadata);
    },
    info(message: string, metadata?: Record<string, unknown>) {
      writeLog("info", scope, message, metadata);
    },
    warn(message: string, metadata?: Record<string, unknown>) {
      writeLog("warn", scope, message, metadata);
    },
    error(message: string, metadata?: Record<string, unknown>) {
      const normalized = metadata?.error
        ? { ...metadata, error: serializeError(metadata.error) }
        : metadata;

      writeLog("error", scope, message, normalized);
    },
  };
}
