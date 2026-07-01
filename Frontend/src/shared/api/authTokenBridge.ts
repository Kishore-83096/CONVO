export type AuthTokenReader = () => Promise<string | null>;

let authTokenReader: AuthTokenReader = async () => null;

export function configureAuthTokenReader(reader: AuthTokenReader): void {
  authTokenReader = reader;
}

export async function readAuthTokenForRequest(): Promise<string | null> {
  return authTokenReader();
}