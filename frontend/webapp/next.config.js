/** @type {import('next').NextConfig} */
const nextConfig = {
	reactStrictMode: true,
	webpack: (config, { isServer }) => {
		// Handle WebAssembly for OpenCV.js and MediaPipe
		config.experiments = {
			...config.experiments,
			asyncWebAssembly: true,
		};

		// Ignore node-specific modules in browser bundle
		if (!isServer) {
			config.resolve.fallback = {
				...config.resolve.fallback,
				fs: false,
				net: false,
				tls: false,
			};
		}

		return config;
	},
	headers: async () => [
		{
			source: "/:path*",
			headers: [
				{ key: "Cross-Origin-Embedder-Policy", value: "require-corp" },
				{ key: "Cross-Origin-Opener-Policy", value: "same-origin" },
			],
		},
	],
};

export default nextConfig;
