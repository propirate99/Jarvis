import { useEffect, useId, useRef, useState } from "react";
import type { CSSProperties, PointerEvent as ReactPointerEvent } from "react";

/* ---------------------------------------------------------------------
   Specular highlight: feeds the pointer position to CSS so a soft light
   follows the cursor across glass controls and cards.
   --------------------------------------------------------------------- */
export function trackPointer(event: ReactPointerEvent<HTMLElement>) {
  const rect = event.currentTarget.getBoundingClientRect();
  event.currentTarget.style.setProperty("--mx", `${event.clientX - rect.left}px`);
  event.currentTarget.style.setProperty("--my", `${event.clientY - rect.top}px`);
}

/* ---------------------------------------------------------------------
   Real refraction (Chromium only, progressive enhancement).
   Builds a displacement map from the element's own rounded shape and uses
   it in an SVG feDisplacementMap as a backdrop-filter, so content under the
   glass bends at the edge like a lens. Safari, Firefox and "reduce
   transparency" keep the plain frosted glass.
   --------------------------------------------------------------------- */
type LensMap = { src: string; width: number; height: number; scale: number };

function canRefract() {
  if (typeof window === "undefined") return false;
  // Disable heavy canvas displacement filter on mobile screens to ensure smooth touch events and performance
  if (window.innerWidth <= 768) return false;
  const isChromium = /Chrome\//.test(navigator.userAgent);
  const reduced = window.matchMedia("(prefers-reduced-transparency: reduce)").matches;
  return isChromium && !reduced && CSS.supports("backdrop-filter", "url(#lens) blur(1px)");
}

function buildLensMap(width: number, height: number, radius: number, bezel: number, depth: number): LensMap | null {
  const w = Math.round(width);
  const h = Math.round(height);
  const k = w * h > 120_000 ? 0.5 : 1; // lower-resolution map for big elements
  const cw = Math.max(1, Math.round(w * k));
  const ch = Math.max(1, Math.round(h * k));

  const canvas = document.createElement("canvas");
  canvas.width = cw;
  canvas.height = ch;
  const context = canvas.getContext("2d");
  if (!context) return null;

  const image = context.createImageData(cw, ch);
  const halfW = w / 2;
  const halfH = h / 2;
  const r = Math.min(radius, halfW, halfH);
  const band = Math.min(bezel, halfW, halfH);

  for (let y = 0; y < ch; y++) {
    for (let x = 0; x < cw; x++) {
      const cx = (x + 0.5) / k - halfW;
      const cy = (y + 0.5) / k - halfH;
      const qx = Math.abs(cx) - (halfW - r);
      const qy = Math.abs(cy) - (halfH - r);
      const ox = Math.max(qx, 0);
      const oy = Math.max(qy, 0);
      const outside = Math.hypot(ox, oy);
      const inset = r - (outside + Math.min(Math.max(qx, qy), 0)); // distance in from the edge

      let dx = 0;
      let dy = 0;
      if (inset < band) {
        const strength = (1 - Math.max(inset, 0) / band) ** 2; // strongest at the very edge
        let nx = 0;
        let ny = 0;
        if (outside > 0) {
          nx = (Math.sign(cx) * ox) / outside;
          ny = (Math.sign(cy) * oy) / outside;
        } else if (qx > qy) {
          nx = Math.sign(cx);
        } else {
          ny = Math.sign(cy);
        }
        dx = -nx * strength; // sample from further inside the glass
        dy = -ny * strength;
      }

      const i = (y * cw + x) * 4;
      image.data[i] = Math.round(127.5 + dx * 127.5);
      image.data[i + 1] = Math.round(127.5 + dy * 127.5);
      image.data[i + 2] = 128;
      image.data[i + 3] = 255;
    }
  }

  context.putImageData(image, 0, 0);
  return { src: canvas.toDataURL(), width: w, height: h, scale: depth * 2 };
}

export function useLiquidLens<T extends HTMLElement>(bezel: number, depth: number) {
  const ref = useRef<T>(null);
  const rawId = useId();
  const id = `lens${rawId.replace(/[^a-zA-Z0-9]/g, "")}`;
  const [map, setMap] = useState<LensMap | null>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element || !canRefract()) return;

    let frame = 0;
    const rebuild = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const { width, height } = element.getBoundingClientRect();
        if (width < 8 || height < 8) return; // hidden tabs have no size yet
        const radius = parseFloat(getComputedStyle(element).borderTopLeftRadius) || 0;
        setMap(buildLensMap(width, height, radius, bezel, depth));
      });
    };

    const observer = new ResizeObserver(rebuild);
    observer.observe(element);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [bezel, depth]);

  const style: CSSProperties | undefined = map
    ? { backdropFilter: `url(#${id}) blur(6px) saturate(190%) brightness(1.08)` }
    : undefined;

  const defs = map ? (
    <svg className="lens-defs" width="0" height="0" aria-hidden="true" focusable="false">
      <defs>
        <filter id={id} filterUnits="userSpaceOnUse" colorInterpolationFilters="sRGB" x={0} y={0} width={map.width} height={map.height}>
          <feImage href={map.src} x={0} y={0} width={map.width} height={map.height} preserveAspectRatio="none" result="map" />
          <feDisplacementMap in="SourceGraphic" in2="map" scale={map.scale} xChannelSelector="R" yChannelSelector="G" />
        </filter>
      </defs>
    </svg>
  ) : null;

  return { ref, style, defs };
}
