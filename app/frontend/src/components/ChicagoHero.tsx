import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  CHICAGO_COMMUNITY_PATHS,
  type ChicagoCommunityPath,
} from "../data/chicagoCommunityPaths";

type MotionMode = "scroll" | "mobile" | "reduced";

interface Fragment extends ChicagoCommunityPath {
  dx: number;
  dy: number;
  rotation: number;
  color: string;
  delay: number;
}

const COLORS = ["#d9957c", "#9e6849", "#b98459", "#715e22", "#efb8a4"];

function buildFragments(): Fragment[] {
  return CHICAGO_COMMUNITY_PATHS.map((area, index) => {
    const skylineColumn = index % 11;
    const skylineLevel = Math.floor(index / 11);
    const startX = 68 + skylineColumn * 43;
    const startY = 440 - skylineLevel * 25 - (skylineColumn % 3) * 4;
    return {
      ...area,
      dx: startX - area.cx,
      dy: startY - area.cy,
      rotation: ((index % 5) - 2) * 1.1,
      color: COLORS[(area.id * 2 + Math.floor(area.cy / 60)) % COLORS.length],
      delay: (index % 11) * 0.018 + Math.floor(index / 11) * 0.004,
    };
  });
}

function getMotionMode(): MotionMode {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return "scroll";
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return "reduced";
  if (window.matchMedia("(max-width: 720px)").matches) return "mobile";
  return "scroll";
}

const clamp = (value: number) => Math.min(1, Math.max(0, value));
const smoothstep = (value: number) => {
  const t = clamp(value);
  return t * t * (3 - 2 * t);
};

function beatOpacity(progress: number, start: number, hold: number, end: number) {
  if (progress < start || progress > end) return 0;
  if (progress <= hold) return smoothstep((progress - start) / Math.max(hold - start, 0.001));
  return 1 - smoothstep((progress - hold) / Math.max(end - hold, 0.001));
}

export function ChicagoHero() {
  const fragments = useMemo(buildFragments, []);
  const sectionRef = useRef<HTMLElement>(null);
  const sceneRef = useRef<HTMLDivElement>(null);
  const animationsRef = useRef<Animation[]>([]);
  const actionsReadyRef = useRef(false);
  const [mode, setMode] = useState<MotionMode>(getMotionMode);
  const [actionsReady, setActionsReady] = useState(mode !== "scroll");

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    const mobile = window.matchMedia("(max-width: 720px)");
    const update = () => setMode(getMotionMode());
    reduced.addEventListener("change", update);
    mobile.addEventListener("change", update);
    return () => {
      reduced.removeEventListener("change", update);
      mobile.removeEventListener("change", update);
    };
  }, []);

  useEffect(() => {
    const section = sectionRef.current;
    const scene = sceneRef.current;
    if (!section || !scene) return;

    animationsRef.current.forEach((animation) => animation.cancel());
    animationsRef.current = [];
    const elements = Array.from(scene.querySelectorAll<SVGPathElement>("[data-hero-fragment]"));

    if (mode === "reduced") {
      elements.forEach((element) => {
        element.style.transform = "none";
        element.style.opacity = "0.96";
      });
      actionsReadyRef.current = true;
      setActionsReady(true);
      return;
    }

    if (elements.some((element) => typeof element.animate !== "function")) {
      elements.forEach((element) => {
        element.style.transform = "none";
        element.style.opacity = "0.96";
      });
      actionsReadyRef.current = true;
      setActionsReady(true);
      return;
    }

    if (mode === "mobile") {
      const animations = elements.map((element, index) => {
        const fragment = fragments[index];
        return element.animate(
          [
            {
              transform: `translate(${fragment.dx * 0.34}px, ${fragment.dy * 0.28}px) rotate(${fragment.rotation}deg)`,
              opacity: 0.25,
            },
            { transform: "translate(0, 0) rotate(0deg)", opacity: 0.96 },
          ],
          {
            duration: 760,
            delay: Math.min((index % 7) * 30, 180),
            easing: "cubic-bezier(0.05, 0.7, 0.1, 1)",
            fill: "both",
          },
        );
      });
      animationsRef.current = animations;
      actionsReadyRef.current = true;
      setActionsReady(true);
      return () => animations.forEach((animation) => animation.cancel());
    }

    const animations = elements.map((element, index) => {
      const fragment = fragments[index];
      const animation = element.animate(
        [
          {
            transform: `translate(${fragment.dx}px, ${fragment.dy}px) rotate(${fragment.rotation}deg)`,
              opacity: 0.44,
          },
          { transform: "translate(0, 0) rotate(0deg)", opacity: 0.96 },
        ],
        {
          duration: 1000,
          easing: "cubic-bezier(0.22, 0.72, 0.18, 1)",
          fill: "both",
        },
      );
      animation.pause();
      animation.currentTime = 0;
      return animation;
    });
    animationsRef.current = animations;

    const beats = Array.from(scene.querySelectorAll<HTMLElement>("[data-hero-beat]"));
    const horizon = scene.querySelector<HTMLElement>("[data-hero-horizon]");
    let frame = 0;

    const render = () => {
      frame = 0;
      const rect = section.getBoundingClientRect();
      const distance = Math.max(section.offsetHeight - window.innerHeight, 1);
      const progress = clamp(-rect.top / distance);

      animations.forEach((animation, index) => {
        const local = clamp((progress - fragments[index].delay) / (0.67 - fragments[index].delay));
        animation.currentTime = local * 1000;
      });

      const opacities = [
        progress <= 0.18 ? 1 : 1 - smoothstep((progress - 0.18) / 0.17),
        beatOpacity(progress, 0.27, 0.4, 0.7),
        smoothstep((progress - 0.64) / 0.19),
      ];
      beats.forEach((beat, index) => {
        const opacity = opacities[index];
        beat.style.opacity = String(opacity);
        beat.style.transform = `translateY(${(1 - opacity) * 24}px)`;
      });
      if (horizon) {
        horizon.style.transform = `translate3d(${progress * -24}px, ${progress * 8}px, 0)`;
        horizon.style.opacity = String(0.7 - progress * 0.35);
      }

      const ready = progress >= 0.78;
      if (ready !== actionsReadyRef.current) {
        actionsReadyRef.current = ready;
        setActionsReady(ready);
      }
    };
    const requestRender = () => {
      if (!frame) frame = window.requestAnimationFrame(render);
    };
    render();
    window.addEventListener("scroll", requestRender, { passive: true });
    window.addEventListener("resize", requestRender);
    return () => {
      if (frame) window.cancelAnimationFrame(frame);
      window.removeEventListener("scroll", requestRender);
      window.removeEventListener("resize", requestRender);
      animations.forEach((animation) => animation.cancel());
    };
  }, [fragments, mode]);

  return (
    <section
      ref={sectionRef}
      className={`hero hero--${mode}`}
      data-motion={mode}
      aria-labelledby="hero-accessible-title"
    >
      <h1 id="hero-accessible-title" className="visually-hidden">
        Chicago, in motion. Seventy-seven community areas, one shared pulse. Ask what changed.
      </h1>
      <div ref={sceneRef} className="hero__sticky">
        <div className="hero__atmosphere" aria-hidden="true">
          <span data-hero-horizon className="hero__horizon" />
          <span className="hero__grain" />
        </div>

        <svg
          className="hero__map"
          viewBox="0 0 528 520"
          role="presentation"
          aria-hidden="true"
        >
          <g className="hero__fragments">
            {fragments.map((fragment) => (
              <path
                key={fragment.id}
                data-testid="hero-fragment"
                data-hero-fragment
                d={fragment.d}
                fill={fragment.color}
              >
                <title>{fragment.name}</title>
              </path>
            ))}
          </g>
        </svg>

        <div className="hero__copy" aria-hidden="true">
          <p data-hero-beat className="hero__beat hero__beat--one">
            Chicago,
            <br />
            in motion.
          </p>
          <p data-hero-beat className="hero__beat hero__beat--two">
            77 community areas.
            <br />
            One shared pulse.
          </p>
          <p data-hero-beat className="hero__beat hero__beat--three">
            Ask what changed.
          </p>
        </div>

        <div
          className={`hero__actions ${actionsReady ? "hero__actions--ready" : ""}`}
          aria-hidden={!actionsReady}
        >
          <Link className="hero__cta hero__cta--primary" to="/ask" tabIndex={actionsReady ? 0 : -1}>
            Ask ChicagoPulse <span aria-hidden="true">→</span>
          </Link>
          <Link className="hero__cta hero__cta--secondary" to="/neighborhoods" tabIndex={actionsReady ? 0 : -1}>
            Explore neighborhoods
          </Link>
        </div>

        <div className="hero__scroll-cue" aria-hidden="true">
          <span>Scroll to open the city</span>
          <span className="hero__scroll-line" />
        </div>
      </div>
    </section>
  );
}
