import { NextRequest, NextResponse } from "next/server"
import { writeFileSync, mkdirSync } from "fs"
import { join } from "path"

export async function POST(request: NextRequest) {
  const { bbox, token, isPanoOnly, areaName } = await request.json() as {
    bbox: [number, number, number, number],
    token: string,
    isPanoOnly: boolean,
    areaName: string
  }

  const [minLng, minLat, maxLng, maxLat] = bbox
  const bboxStr = `${minLng},${minLat},${maxLng},${maxLat}`
  const isPanoParam = isPanoOnly ? "&is_pano=true" : ""
  const url = `https://graph.mapillary.com/images?bbox=${bboxStr}&access_token=${token}&fields=id,captured_at,thumb_2048_url&limit=2000${isPanoParam}`

  const response = await fetch(url)
  const data = await response.json()

  if (!data.data || data.data.length === 0) {
    return NextResponse.json({ success: false, error: "No images found in selected area" }, { status: 404 })
  }

  const outputDir = join(process.cwd(), "..", "lidar_data", areaName, "images")
  mkdirSync(outputDir, { recursive: true })

  const imageData = data.data.sort((a: any, b: any) => a.captured_at - b.captured_at)
  let saved = 0

  for (let i = 0; i < imageData.length; i++) {
    const img = imageData[i]
    try {
      const meta = await fetch(`https://graph.mapillary.com/${img.id}?fields=thumb_2048_url&access_token=${token}`)
      const metaData = await meta.json()
      if (metaData.thumb_2048_url) {
        const imageRes = await fetch(metaData.thumb_2048_url)
        const buffer = Buffer.from(await imageRes.arrayBuffer())
        const filename = `${String(i + 1).padStart(4, "0")}_${img.id}.jpg`
        writeFileSync(join(outputDir, filename), buffer)
        saved++
      }
    } catch (err) {
      console.error(`Failed to save image ${img.id}:`, err)
    }
  }

  return NextResponse.json({ success: true, saved, outputDir })
}
