import React from 'react';
const DEFAULT_SRC = 'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260613_180732_a54afbf6-b30d-470e-861f-669871f09f67.mp4';
export function BackgroundVideo({ src = DEFAULT_SRC, poster }) {
  return <video className="nx-video" src={src} poster={poster} autoPlay muted loop playsInline></video>;
}
