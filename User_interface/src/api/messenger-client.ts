import env from "@/config/env";

import { createHttpClient } from "./http-client";

const messengerClient = createHttpClient(
  env.messengerApiBaseUrl,
);

export default messengerClient;