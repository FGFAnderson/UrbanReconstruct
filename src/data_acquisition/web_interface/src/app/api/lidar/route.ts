import { NextRequest, NextResponse } from 'next/server'
import { spawn } from 'child_process'
import { writeFileSync, mkdirSync } from 'fs'
import { join } from 'path'
import os from 'os'

export async function POST(request: NextRequest) {
  const { bbox, types } = await request.json() as {
    bbox: [number, number, number, number],
    types: string[]
  }

  const [minLng, minLat, maxLng, maxLat] = bbox

  const geojsonPath = join(os.tmpdir(), `lidar_bbox_${Date.now()}.geojson`)
  writeFileSync(geojsonPath, JSON.stringify({
    type: "FeatureCollection",
    features: [{
      type: "Feature",
      properties: {},
      geometry: {
        type: "Polygon",
        coordinates: [[
          [minLng, minLat],
          [maxLng, minLat],
          [maxLng, maxLat],
          [minLng, maxLat],
          [minLng, minLat]
        ]]
      }
    }]
  }))

  const outputDir = join(process.cwd(), '..', 'lidar_data')
  mkdirSync(outputDir, { recursive: true })

  const scriptPath = join(process.cwd(), '..', 'lidar', 'ea_lidar.py')
  const python = join(process.cwd(), '..', '..', '..', '.venv', 'bin', 'python')

  const args = [scriptPath, geojsonPath, '--odir', outputDir]
  if (types.includes('dtm')) args.push('--dtm')
  if (types.includes('dsm')) args.push('--dsm')
  if (types.includes('point_cloud')) args.push('--point-cloud')

  return new Promise<NextResponse>((resolve) => {
    const proc = spawn(python, args)

    let stdout = ''
    let stderr = ''

    proc.stdout.on('data', (d) => { stdout += d.toString() })
    proc.stderr.on('data', (d) => { stderr += d.toString() })

    proc.on('close', (code) => {
      if (code === 0) {
        resolve(NextResponse.json({ success: true, output: stdout, outputDir }))
      } else {
        resolve(NextResponse.json({ success: false, error: stderr || stdout }, { status: 500 }))
      }
    })
  })
}
