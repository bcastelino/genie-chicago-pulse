import { useEffect, useMemo, useRef, useState } from "react";
import { IconSearch } from "./icons";

export interface Option {
  value: number;
  label: string;
}

/** Accessible, searchable combobox (WAI-ARIA combobox + listbox pattern). */
export function NeighborhoodSelect({
  id,
  label,
  options,
  value,
  onChange,
  placeholder = "Search neighborhoods…",
}: {
  id: string;
  label: string;
  options: Option[];
  value: number | null;
  onChange: (value: number) => void;
  placeholder?: string;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);

  const selected = options.find((o) => o.value === value) ?? null;

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => o.label.toLowerCase().includes(q));
  }, [options, query]);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  const displayValue = open ? query : selected?.label ?? "";

  function commit(opt: Option) {
    onChange(opt.value);
    setQuery("");
    setOpen(false);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((a) => Math.min(a + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      if (open && filtered[active]) {
        e.preventDefault();
        commit(filtered[active]);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  const listId = `${id}-list`;
  return (
    <div className="field combo" ref={rootRef}>
      <label htmlFor={id}>{label}</label>
      <div style={{ position: "relative" }}>
        <IconSearch className="combo__icon" size={16} />
        <input
          id={id}
          name={id}
          className="input combo__input"
          type="text"
          autoComplete="off"
          spellCheck={false}
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={open && filtered[active] ? `${id}-opt-${filtered[active].value}` : undefined}
          placeholder={placeholder}
          value={displayValue}
          onFocus={() => {
            setOpen(true);
            setActive(0);
          }}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
            setActive(0);
          }}
          onKeyDown={onKeyDown}
        />
      </div>
      {open && (
        <ul className="combo__list" id={listId} role="listbox" aria-label={label}>
          {filtered.length === 0 && <li className="combo__empty">No neighborhoods match “{query}”.</li>}
          {filtered.map((o, i) => (
            <li
              key={o.value}
              id={`${id}-opt-${o.value}`}
              role="option"
              aria-selected={o.value === value}
              className={`combo__option ${i === active ? "active" : ""}`}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => {
                e.preventDefault();
                commit(o);
              }}
            >
              <span>{o.label}</span>
              <span className="num">#{o.value}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
