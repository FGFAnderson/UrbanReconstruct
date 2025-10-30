"use client"

import { useEffect, useRef } from "react"
import maplibregl from "maplibre-gl"
import "maplibre-gl/dist/maplibre-gl.css"

interface MapProps {
  position: [number, number];
  zoom: number;
}

export default function Map({ position, zoom }: MapProps) {
  const mapContainer = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map>()

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
        id: "panos",
        type: "circle",
        source: "mapillary",
        "source-layer": "sequence",
        filter: ["==", ["get", "is_pano"], true],
        paint: {
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["zoom"],
            10, 3,
            16, 6,
            22, 10
          ],
          "circle-color": "#05CB63",
          "circle-stroke-width": 1,
          "circle-stroke-color": "#ffffff",
        }
      })
      
      map.on("mouseenter", "panos", () => {
        map.getCanvas().style.cursor = "pointer"
      })

      map.on("mouseleave", "panos", () => {
        map.getCanvas().style.cursor = ""
      })

      map.on("click", "panos", (e) => {
        console.log("Clicked:", e.features?.[0].properties)
      })
    })

    return () => map.remove()
  }, [])

  useEffect(() => {
    mapRef.current?.setCenter(position)
    mapRef.current?.setZoom(zoom)
  }, [position, zoom])

  return <div ref={mapContainer} style={{ width: "100%", height: "100%" }} />
}