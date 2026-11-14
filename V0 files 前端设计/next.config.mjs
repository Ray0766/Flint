/** @type {import('next').NextConfig} */
const nextConfig = {
  // v0 出厂默认开着 typescript.ignoreBuildErrors——那会让契约镜像偏离在构建期静默通过。
  // 本前端消费冻结件镜像，类型错必须炸在构建期，故移除该开关（等价于 false）。
  images: {
    unoptimized: true,
  },
}

export default nextConfig
