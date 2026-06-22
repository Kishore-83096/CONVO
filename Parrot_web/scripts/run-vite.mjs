import process from "node:process"
import { createInterface } from "node:readline/promises"
import { parseArgs } from "node:util"

import { createServer, loadEnv } from "vite"

const environments = new Set(["development", "production"])

function validateEnvironment(environment) {
  const normalizedEnvironment = environment?.trim().toLowerCase()

  if (!environments.has(normalizedEnvironment)) {
    throw new Error("Enter either 'development' or 'production'.")
  }

  return normalizedEnvironment
}

async function selectEnvironment() {
  const { values } = parseArgs({
    options: {
      env: {
        type: "string",
      },
    },
  })

  if (values.env) {
    return validateEnvironment(values.env)
  }

  if (!process.stdin.isTTY) {
    throw new Error(
      "Environment is missing. Run with --env development or --env production.",
    )
  }

  const prompt = createInterface({
    input: process.stdin,
    output: process.stdout,
  })

  try {
    const selection = await prompt.question(
      "Select environment [development/production]: ",
    )

    return validateEnvironment(selection)
  } finally {
    prompt.close()
  }
}

async function main() {
  const environment = await selectEnvironment()
  const environmentVariables = loadEnv(environment, process.cwd(), "VITE_")

  if (!environmentVariables.VITE_IDENTITY_API_BASE_URL) {
    throw new Error(
      `VITE_IDENTITY_API_BASE_URL is missing from .env.${environment}.`,
    )
  }

  const server = await createServer({ mode: environment })

  await server.listen()

  console.log(`Loaded .env.${environment}`)
  server.printUrls()
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error)
  process.exitCode = 1
})
