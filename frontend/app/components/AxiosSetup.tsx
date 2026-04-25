"use client";
import axios from "axios";
import { useEffect } from "react";

// Set immediately at module eval time (client bundle only).
axios.defaults.withCredentials = true;

export default function AxiosSetup() {
  useEffect(() => {
    axios.defaults.withCredentials = true;
  }, []);
  return null;
}
