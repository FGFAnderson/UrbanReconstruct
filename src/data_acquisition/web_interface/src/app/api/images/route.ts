import { NextRequest, NextResponse } from "next/server";
import { writeFileSync, mkdirSync } from "fs";
import { join } from "path";
import piexif from "piexifjs";

function decimalToRational(
  decimal: number,
): [[number, number], [number, number], [number, number]] {
  const d = Math.floor(Math.abs(decimal));
  const mFloat = (Math.abs(decimal) - d) * 60;
  const m = Math.floor(mFloat);
  const s = Math.round((mFloat - m) * 60 * 1000);
  return [
    [d, 1],
    [m, 1],
    [s, 1000],
  ];
}

export async function POST(request: NextRequest) {
  const { bbox, token, isPanoOnly, areaName } = (await request.json()) as {
    bbox: [number, number, number, number];
    token: string;
    isPanoOnly: boolean;
    areaName: string;
  };

  const [minLng, minLat, maxLng, maxLat] = bbox;
  const bboxStr = `${minLng},${minLat},${maxLng},${maxLat}`;
  const isPanoParam = isPanoOnly ? "&is_pano=true" : "";
  const url = `https://graph.mapillary.com/images?bbox=${bboxStr}&access_token=${token}&fields=id,captured_at,thumb_2048_url&limit=2000${isPanoParam}`;

  const response = await fetch(url);
  const data = await response.json();

  if (!data.data || data.data.length === 0) {
    return NextResponse.json(
      { success: false, error: "No images found in selected area" },
      { status: 404 },
    );
  }

  const outputDir = join(process.cwd(), "..", "geo_data", areaName, "images");
  mkdirSync(outputDir, { recursive: true });

  const imageData = data.data.sort(
    (a: any, b: any) => a.captured_at - b.captured_at,
  );
  let saved = 0;
  const sidecar: object[] = [];

  for (let i = 0; i < imageData.length; i++) {
    const img = imageData[i];
    try {
      const meta = await fetch(
        `https://graph.mapillary.com/${img.id}?fields=thumb_2048_url,geometry,compass_angle,altitude&access_token=${token}`,
      );
      const metaData = await meta.json();
      if (metaData.thumb_2048_url) {
        const imageRes = await fetch(metaData.thumb_2048_url);
        const buffer = Buffer.from(await imageRes.arrayBuffer());

        // Writing to exif and json for use further down the pipeline
        // exif data is also used in some other tools which will be evaluated
        const exifObj: { [ifd: string]: { [tag: number]: any } } = {
          "0th": {},
          Exif: {},
          GPS: {},
        };

        const date = new Date(img.captured_at);
        const dateStr = `${date.getUTCFullYear()}:${String(date.getUTCMonth() + 1).padStart(2, "0")}:${String(date.getUTCDate()).padStart(2, "0")} ${String(date.getUTCHours()).padStart(2, "0")}:${String(date.getUTCMinutes()).padStart(2, "0")}:${String(date.getUTCSeconds()).padStart(2, "0")}`;
        exifObj["0th"][piexif.ImageIFD.DateTime] = dateStr;
        exifObj["Exif"][piexif.ExifIFD.DateTimeOriginal] = dateStr;

        const record: Record<string, any> = {
          filename: `${String(i + 1).padStart(4, "0")}_${img.id}.jpg`,
          mapillary_id: img.id,
          captured_at: new Date(img.captured_at).toISOString(),
        };

        if (metaData.geometry?.coordinates) {
          const [lng, lat] = metaData.geometry.coordinates;
          exifObj["GPS"][piexif.GPSIFD.GPSLatitudeRef] = lat >= 0 ? "N" : "S";
          exifObj["GPS"][piexif.GPSIFD.GPSLatitude] = decimalToRational(lat);
          exifObj["GPS"][piexif.GPSIFD.GPSLongitudeRef] = lng >= 0 ? "E" : "W";
          exifObj["GPS"][piexif.GPSIFD.GPSLongitude] = decimalToRational(lng);
          record.latitude = lat;
          record.longitude = lng;
        }

        if (metaData.altitude != null && metaData.altitude !== 0) {
          exifObj["GPS"][piexif.GPSIFD.GPSAltitudeRef] =
            metaData.altitude >= 0 ? 0 : 1;
          exifObj["GPS"][piexif.GPSIFD.GPSAltitude] = [
            Math.round(Math.abs(metaData.altitude) * 100),
            100,
          ];
          record.altitude = metaData.altitude;
        }

        if (metaData.compass_angle != null) {
          exifObj["GPS"][piexif.GPSIFD.GPSImgDirectionRef] = "T";
          exifObj["GPS"][piexif.GPSIFD.GPSImgDirection] = [
            Math.round(metaData.compass_angle * 100),
            100,
          ];
          record.compass_angle = metaData.compass_angle;
        }

        const exifBytes = piexif.dump(exifObj);
        const newBuffer = Buffer.from(
          piexif.insert(exifBytes, buffer.toString("binary")),
          "binary",
        );

        const filename = `${String(i + 1).padStart(4, "0")}_${img.id}.jpg`;
        writeFileSync(join(outputDir, filename), newBuffer);
        sidecar.push(record);
        saved++;
      }
    } catch (err) {
      console.error(`Failed to save image ${img.id}:`, err);
    }
  }

  writeFileSync(
    join(outputDir, "metadata.json"),
    JSON.stringify(
      {
        area: {
          name: areaName,
          bbox: { minLng, minLat, maxLng, maxLat },
          isPanoOnly,
          downloaded_at: new Date().toISOString(),
          image_count: saved,
        },
        images: sidecar,
      },
      null,
      2,
    ),
  );

  return NextResponse.json({ success: true, saved, outputDir });
}
