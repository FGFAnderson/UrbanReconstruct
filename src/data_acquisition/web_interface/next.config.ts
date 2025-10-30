import type { NextConfig } from "next";

const path = require('path')

require('dotenv').config({ 
  path: path.resolve(__dirname, '../../../.env') 
})


/** @type {import('next').NextConfig} */
const nextConfig = {
  reactCompiler: true,
};

module.exports = nextConfig;

export default nextConfig;
