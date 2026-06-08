/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  // add other VITE_ env vars here as needed
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// Allow importing css?url from Vite
declare module '*.css?url' {
  const url: string;
  export default url;
}
