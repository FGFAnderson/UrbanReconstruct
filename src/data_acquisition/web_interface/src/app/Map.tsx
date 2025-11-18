"use client"
import { useEffect, useRef, useState } from "react"
import maplibregl from "maplibre-gl"
import "maplibre-gl/dist/maplibre-gl.css"
import JSZip from "jszip"

interface MapProps {
  position: [number, number];
  zoom: number;
}

export default function Map({ position, zoom }: MapProps) {
  const mapContainer = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map>(null)
  const [selectedSequenceId, setSelectedSequenceId] = useState<string | null>(null)
  const [isDownloading, setIsDownloading] = useState(false)
  const [downloadProgress, setDownloadProgress] = useState({ current: 0, total: 0 })
  const [imageCount, setImageCount] = useState(0)
  const [showPanosOnly, setShowPanosOnly] = useState(true)
  const [isDrawingBox, setIsDrawingBox] = useState(false)
  const [boxCoords, setBoxCoords] = useState<[number, number, number, number] | null>(null)

  const downloadImages = async () => {
    if (!selectedSequenceId) return
    
    setIsDownloading(true)
    setDownloadProgress({ current: 0, total: 0 })
    
    try {
      const map = mapRef.current
      if (!map) return

      const token = process.env.NEXT_PUBLIC_MAPILLARY_TOKEN
      if (!token) {
        alert("Mapillary token not found, set in .env")
        return
      }

      const filterConditions = showPanosOnly 
        ? ["all", ["==", ["get", "is_pano"], true], ["==", ["get", "sequence_id"], selectedSequenceId]]
        : ["==", ["get", "sequence_id"], selectedSequenceId]

      const features = map.querySourceFeatures("mapillary", {
        sourceLayer: "image",
        filter: filterConditions
      })

      const imageData = features
        .map(feature => ({
          id: feature.properties?.id,
          captured_at: feature.properties?.captured_at,
          compass_angle: feature.properties?.compass_angle,
          coordinates: feature.geometry.type === "Point" ? feature.geometry.coordinates : null
        }))
        .filter(img => img.id)
        .sort((a, b) => (a.captured_at || 0) - (b.captured_at || 0))

      setDownloadProgress({ current: 0, total: imageData.length })

      const zip = new JSZip()

      for (let i = 0; i < imageData.length; i++) {
        const imageInfo = imageData[i]
        setDownloadProgress({ current: i + 1, total: imageData.length })

        try {
          const imageUrl = `https://graph.mapillary.com/${imageInfo.id}?fields=thumb_2048_url&access_token=${token}`
          const response = await fetch(imageUrl)
          const data = await response.json()

          if (data.thumb_2048_url) {
            const imageResponse = await fetch(data.thumb_2048_url)
            const blob = await imageResponse.blob()

            const filename = `${selectedSequenceId}_${String(i + 1).padStart(4, "0")}_${imageInfo.id}.jpg`
            zip.file(filename, blob)

            await new Promise(resolve => setTimeout(resolve, 500))
          }
        } catch (error) {
          console.error(`Error downloading image ${imageInfo.id}:`, error)
        }
      }

      const zipBlob = await zip.generateAsync({ type: "blob" })
      const url = URL.createObjectURL(zipBlob)
      const link = document.createElement("a")
      link.href = url
      link.download = `mapillary_sequence_${selectedSequenceId}.zip`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    } catch (error) {
      console.error("Error downloading sequence:", error)
      alert("Failed to download sequence images")
    } finally {
      setIsDownloading(false)
      setDownloadProgress({ current: 0, total: 0 })
    }
  }

  useEffect(() => {
    if (!mapContainer.current) return

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          "esri-satellite": {
            type: "raster",
            tiles: [
              "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            ],
            tileSize: 256,
          }
        },
        layers: [{
          id: "esri-satellite",
          type: "raster",
          source: "esri-satellite",
        }]
      },
      center: position,
      zoom: zoom,
    })

    mapRef.current = map

    map.on("load", () => {
      const token = process.env.NEXT_PUBLIC_MAPILLARY_TOKEN
      if (!token) return

      map.addSource("mapillary", {
        type: "vector",
        tiles: [`https://tiles.mapillary.com/maps/vtp/mly1_public/2/{z}/{x}/{y}?access_token=${token}`],
      })

      map.addLayer({
        id: "panos-sequence",
        type: "line",
        source: "mapillary",
        "source-layer": "sequence",
        minzoom: 6,
        maxzoom: 14,
        filter: ["==", ["get", "is_pano"], true] as any,
        paint: {
          "line-width": [
            "interpolate",
            ["linear"],
            ["zoom"],
            6, 1.5,
            10, 2,
            14, 3
          ],
          "line-color": "#05CB63",
          "line-opacity": 0.8
        }
      })

      map.addLayer({
        id: "panos-image",
        type: "circle",
        source: "mapillary",
        "source-layer": "image",
        filter: ["==", ["get", "is_pano"], true] as any,
        paint: {
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["zoom"],
            14, 3,
            16, 6,
          ],
          "circle-color": "#05CB63",
          "circle-stroke-width": 1,
          "circle-stroke-color": "#ffffff",
        }
      })
      
      map.addLayer({
        id: "panos-image-highlighted",
        type: "circle",
        source: "mapillary",
        "source-layer": "image",
        filter: ["all",
          ["==", ["get", "is_pano"], true],
          ["==", ["get", "sequence_id"], ""]
        ] as any,
        paint: {
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["zoom"],
            14, 3,
            16, 8,
          ],
          "circle-color": "#FFD700",
          "circle-stroke-width": 2,
          "circle-stroke-color": "#FF6B00",
        }
      })

      map.on("mouseenter", "panos-image", () => {
        if (!isDrawingBox) map.getCanvas().style.cursor = "pointer"
      })
      map.on("mouseleave", "panos-image", () => {
        if (!isDrawingBox) map.getCanvas().style.cursor = ""
      })
      map.on("click", "panos-image", (e) => {
        if (isDrawingBox) return
        const feature = e.features?.[0]
        if (feature?.properties) {
          const sequenceId = feature.properties.sequence_id
          setSelectedSequenceId(sequenceId)
          console.log("Selected sequence (from image layer):", sequenceId)
        }
      })
    })

    return () => map.remove()
  }, [])

  // Handle box drawing
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    if (isDrawingBox) {
      // Disable map interactions
      map.dragPan.disable()
      map.boxZoom.disable()
      map.doubleClickZoom.disable()
      map.getCanvas().style.cursor = "crosshair"

      let startLngLat: maplibregl.LngLat | null = null
      let currentLngLat: maplibregl.LngLat | null = null

      const onMouseDown = (e: maplibregl.MapMouseEvent) => {
        startLngLat = e.lngLat
        currentLngLat = e.lngLat
        
        // Remove existing box if any
        if (map.getSource('temp-bbox')) {
          map.removeLayer('temp-bbox-fill')
          map.removeLayer('temp-bbox-outline')
          map.removeSource('temp-bbox')
        }
      }

      const onMouseMove = (e: maplibregl.MapMouseEvent) => {
        if (!startLngLat) return
        
        currentLngLat = e.lngLat

        const minLng = Math.min(startLngLat.lng, currentLngLat.lng)
        const maxLng = Math.max(startLngLat.lng, currentLngLat.lng)
        const minLat = Math.min(startLngLat.lat, currentLngLat.lat)
        const maxLat = Math.max(startLngLat.lat, currentLngLat.lat)

        const boxData = {
          type: 'Feature' as const,
          properties: {},
          geometry: {
            type: 'Polygon' as const,
            coordinates: [[
              [minLng, minLat],
              [maxLng, minLat],
              [maxLng, maxLat],
              [minLng, maxLat],
              [minLng, minLat]
            ]]
          }
        }

        if (map.getSource('temp-bbox')) {
          (map.getSource('temp-bbox') as maplibregl.GeoJSONSource).setData(boxData)
        } else {
          map.addSource('temp-bbox', {
            type: 'geojson',
            data: boxData
          })

          map.addLayer({
            id: 'temp-bbox-fill',
            type: 'fill',
            source: 'temp-bbox',
            paint: {
              'fill-color': '#05CB63',
              'fill-opacity': 0.1
            }
          })

          map.addLayer({
            id: 'temp-bbox-outline',
            type: 'line',
            source: 'temp-bbox',
            paint: {
              'line-color': '#05CB63',
              'line-width': 2,
              'line-dasharray': [2, 2]
            }
          })
        }
      }

      const onMouseUp = (e: maplibregl.MapMouseEvent) => {
        if (!startLngLat) return

        currentLngLat = e.lngLat

        const minLng = Math.min(startLngLat.lng, currentLngLat.lng)
        const maxLng = Math.max(startLngLat.lng, currentLngLat.lng)
        const minLat = Math.min(startLngLat.lat, currentLngLat.lat)
        const maxLat = Math.max(startLngLat.lat, currentLngLat.lat)

        setBoxCoords([minLng, minLat, maxLng, maxLat])

        // Remove temp box
        if (map.getSource('temp-bbox')) {
          map.removeLayer('temp-bbox-fill')
          map.removeLayer('temp-bbox-outline')
          map.removeSource('temp-bbox')
        }

        // Add final box
        if (map.getSource('bbox')) {
          map.removeLayer('bbox-fill')
          map.removeLayer('bbox-outline')
          map.removeSource('bbox')
        }

        map.addSource('bbox', {
          type: 'geojson',
          data: {
            type: 'Feature',
            properties: {},
            geometry: {
              type: 'Polygon',
              coordinates: [[
                [minLng, minLat],
                [maxLng, minLat],
                [maxLng, maxLat],
                [minLng, maxLat],
                [minLng, minLat]
              ]]
            }
          }
        })

        map.addLayer({
          id: 'bbox-fill',
          type: 'fill',
          source: 'bbox',
          paint: {
            'fill-color': '#05CB63',
            'fill-opacity': 0.2
          }
        })

        map.addLayer({
          id: 'bbox-outline',
          type: 'line',
          source: 'bbox',
          paint: {
            'line-color': '#05CB63',
            'line-width': 3
          }
        })

        setIsDrawingBox(false)
        startLngLat = null
        currentLngLat = null
      }

      map.on('mousedown', onMouseDown)
      map.on('mousemove', onMouseMove)
      map.on('mouseup', onMouseUp)

      return () => {
        map.off('mousedown', onMouseDown)
        map.off('mousemove', onMouseMove)
        map.off('mouseup', onMouseUp)
        map.dragPan.enable()
        map.boxZoom.enable()
        map.doubleClickZoom.enable()
        map.getCanvas().style.cursor = ""
      }
    } else {
      map.dragPan.enable()
      map.boxZoom.enable()
      map.doubleClickZoom.enable()
      map.getCanvas().style.cursor = ""
    }
  }, [isDrawingBox])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.getLayer("panos-image")) return

    const baseFilter = showPanosOnly ? ["==", ["get", "is_pano"], true] : ["has", "id"]
    map.setFilter("panos-sequence", baseFilter as any)
    map.setFilter("panos-image", baseFilter as any)
    
    const highlightFilter = showPanosOnly
      ? ["all", ["==", ["get", "is_pano"], true], ["==", ["get", "sequence_id"], selectedSequenceId || ""]]
      : ["==", ["get", "sequence_id"], selectedSequenceId || ""]
    map.setFilter("panos-image-highlighted", highlightFilter as any)

    if (selectedSequenceId) {
      const filterConditions = showPanosOnly 
        ? ["all", ["==", ["get", "is_pano"], true], ["==", ["get", "sequence_id"], selectedSequenceId]]
        : ["==", ["get", "sequence_id"], selectedSequenceId]

      const features = map.querySourceFeatures("mapillary", {
        sourceLayer: "image",
        filter: filterConditions as any
      })
      setImageCount(features.length)
    } else {
      setImageCount(0)
    }
  }, [showPanosOnly, selectedSequenceId])

  useEffect(() => {
    mapRef.current?.setCenter(position)
    mapRef.current?.setZoom(zoom)
  }, [position, zoom])

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <div ref={mapContainer} style={{ width: "100%", height: "100%" }} />
      
      <div style={{ position: "absolute", top: "10px", left: "10px", display: "flex", gap: "10px" }}>
        <button
          onClick={() => setShowPanosOnly(!showPanosOnly)}
          style={{
            padding: "10px 15px",
            backgroundColor: showPanosOnly ? "#05CB63" : "#666",
            color: "white",
            border: "none",
            fontWeight: "bold",
            cursor: "pointer",
            borderRadius: "4px",
          }}
        >
          {showPanosOnly ? "Panos Only" : "All Images"}
        </button>

        <button
          onClick={() => {
            setIsDrawingBox(!isDrawingBox)
            if (!isDrawingBox) {
              setBoxCoords(null)
              const map = mapRef.current
              if (map?.getSource('bbox')) {
                map.removeLayer('bbox-fill')
                map.removeLayer('bbox-outline')
                map.removeSource('bbox')
              }
            }
          }}
          style={{
            padding: "10px 15px",
            backgroundColor: isDrawingBox ? "#FF6B00" : "#05CB63",
            color: "white",
            border: "none",
            fontWeight: "bold",
            cursor: "pointer",
            borderRadius: "4px",
          }}
        >
          {isDrawingBox ? "Cancel Box" : "Draw Box"}
        </button>
      </div>

      <div style={{ position: "absolute", top: "10px", right: "10px", display: "flex", gap: "10px" }}>
        {selectedSequenceId && (
          <button
            onClick={downloadImages}
            disabled={isDownloading}
            style={{
              padding: "10px 15px",
              backgroundColor: "#05CB63",
              color: "white",
              border: "none",
              fontWeight: "bold",
              cursor: isDownloading ? "not-allowed" : "pointer",
              opacity: isDownloading ? 0.7 : 1,
              borderRadius: "4px",
            }}
          >
            {isDownloading 
              ? `Downloading ${downloadProgress.current}/${downloadProgress.total}` 
              : `Download Sequence (${imageCount})`}
          </button>
        )}

      </div>
    </div>
  )
}