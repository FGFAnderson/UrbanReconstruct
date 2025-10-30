"use client"

import { MapContainer, TileLayer, useMap } from "react-leaflet"
import "leaflet/dist/leaflet.css"
import L, { LatLngExpression } from "leaflet"
import { useEffect } from "react"

function MapillaryLayer() {
  const map = useMap()
  
  useEffect(() => {
    import('leaflet.vectorgrid').then(() => {
      const MAPILLARY_TOKEN = process.env.NEXT_PUBLIC_MAPILLARY_TOKEN
      
      const mapillaryLayer = (L as any).vectorGrid.protobuf(
        `https://tiles.mapillary.com/maps/vtp/mly1_public/2/{z}/{x}/{y}?access_token=${MAPILLARY_TOKEN}`,
        {
          vectorTileLayerStyles: {
            sequence: function(properties: any) {
              if (!properties.is_pano) {
                return {
                  opacity: 0,
                }
              }
              return {
                radius: 1,
                weight: 1,
                color: '#05CB63',
                fillColor: '#05CB63',
                fillOpacity: 0.8
              }
            },
            image: {
                opacity: 0
            },
            overview: {
                opacity: 0
            },
          },
          maxNativeZoom: 14,
          interactive: true,
          getFeatureId: function(f: any) {
            return f.properties.id
          }
        }
      ).addTo(map)
      
      mapillaryLayer.on('click', function(e: any) {
        if (e.layer.properties) {
          console.log('Clicked:', e.layer.properties)
        }
      })
    })
  }, [map])
  
  return null
}

interface MapProps {
  position: LatLngExpression | undefined;
  zoom: number;
}

export default function Map({position, zoom}: MapProps) {
  
  return <MapContainer center={position} zoom={zoom} scrollWheelZoom={true} style={{ height: "100%", width: "100%" }}>
    <TileLayer
      attribution="Esri"
      url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    />
    <MapillaryLayer></MapillaryLayer>
  </MapContainer>
}