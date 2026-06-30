import env from "@/config/env";

import { createHttpClient } from "./http-client";

const identityClient = createHttpClient(
  env.identityApiBaseUrl,
);

export default identityClient;