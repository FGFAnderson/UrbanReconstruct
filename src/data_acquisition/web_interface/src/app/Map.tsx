"use client"
import { useEffect, useRef, useState } from "react"
import maplibregl from "maplibre-gl"
import "maplibre-gl/dist/maplibre-gl.css"

interface MapProps {
  position: [number, number];
  zoom: number;
}

export default function Map({ position, zoom }: MapProps) {
  const mapContainer = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map>()
  const [selectedSequenceId, setSelectedSequenceId] = useState<string | null>(null)

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
        filter: ["==", ["get", "is_pano"], true],
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
        filter: ["==", ["get", "is_pano"], true],
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
        ],
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
        map.getCanvas().style.cursor = "pointer"
      })
      map.on("mouseleave", "panos-image", () => {
        map.getCanvas().style.cursor = ""
      })
      map.on("click", "panos-image", (e) => {
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

  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    if (map.getLayer("panos-image-highlighted")) {
      if (selectedSequenceId) {
        map.setFilter("panos-image-highlighted", [
          "all",
          ["==", ["get", "is_pano"], true],
          ["==", ["get", "sequence_id"], selectedSequenceId]
        ])
      } else {
        map.setFilter("panos-image-highlighted", [
          "all",
          ["==", ["get", "is_pano"], true],
          ["==", ["get", "sequence_id"], ""]
        ])
      }
    }
  }, [selectedSequenceId])

  useEffect(() => {
    mapRef.current?.setCenter(position)
    mapRef.current?.setZoom(zoom)
  }, [position, zoom])

  return <div ref={mapContainer} style={{ width: "100%", height: "100%" }} />
}