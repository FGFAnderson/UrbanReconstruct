"use client"

import dynamic from "next/dynamic";
import styles from "./page.module.css";

const Map = dynamic(() => import("./Map"), {
  ssr: false,
  loading: () => <div>Loading map...</div>
});

export default function Home() {
  return (
    <div className={styles.page}>
      <Map position={[-0.09, 51.505]} zoom={13} />
    </div>
  );
}