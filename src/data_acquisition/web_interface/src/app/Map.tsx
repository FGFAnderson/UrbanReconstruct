"use client"

import { MapContainer, TileLayer } from "react-leaflet"
import "leaflet/dist/leaflet.css"

export default function Map(props: any) {
  const { position, zoom } = props

  return <MapContainer center={position} zoom={zoom} scrollWheelZoom={true} style={{ height: "100%", width: "100%" }}>
    <TileLayer
    attribution="Esri"
    url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    />
  </MapContainer>
}