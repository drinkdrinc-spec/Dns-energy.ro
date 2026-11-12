import { Link } from "react-router-dom";
import { ArrowUpRight, Zap } from "lucide-react";
import { BrandMark } from "@/components/BrandMark";

export default function ComingSoon() {
  return <main className="min-h-screen flex flex-col" style={{ background: "var(--bg)" }}>
    <header className="flex h-16 items-center gap-3 px-5 sm:px-8 text-white" style={{ background: "var(--navy)" }}>
      <BrandMark size={36} />
      <div className="font-extrabold tracking-wide">D-ENERGY</div>
      <span className="ml-1 text-xs" style={{ color: "#aab8d1" }}>DNS HOSTESS S.R.L.</span>
    </header>
    <section className="mx-auto flex w-full max-w-5xl flex-1 flex-col justify-center px-5 py-16 sm:px-10 lg:flex-row lg:items-center lg:gap-16">
      <div className="max-w-2xl">
        <div className="mb-5 inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-bold" style={{ color: "var(--green)", borderColor: "#b8d8c0", background: "#edf7f0" }}><span className="h-2 w-2 rounded-full" style={{ background: "var(--green)" }} /> Platformă în pregătire</div>
        <h1 className="text-4xl font-extrabold leading-tight sm:text-6xl" style={{ color: "var(--ink)" }}>DNS Energy<br /><span style={{ color: "var(--green)" }}>în curând.</span></h1>
        <p className="mt-5 max-w-xl text-base leading-relaxed sm:text-lg" style={{ color: "var(--muted)" }}>Pregătim un spațiu simplu pentru gestionarea dosarelor electrice și fotovoltaice, de la datele clientului până la documentația tehnică.</p>
        <div className="mt-8 flex flex-wrap items-center gap-3">
          <span className="inline-flex items-center gap-2 rounded-xl px-4 py-3 text-sm font-bold text-white" style={{ background: "var(--green)" }}><Zap size={16} /> Revenim în curând</span>
          <Link to="/login" className="inline-flex items-center gap-1.5 rounded-xl border bg-white px-4 py-3 text-sm font-semibold transition hover:bg-slate-50" style={{ borderColor: "var(--line)", color: "var(--ink)" }}>Acces administrator <ArrowUpRight size={15} /></Link>
        </div>
      </div>
      <div className="mt-14 hidden h-64 w-64 shrink-0 place-items-center rounded-[2rem] border lg:grid" style={{ borderColor: "#dce9dc", background: "linear-gradient(145deg,#edf7f0,#fffefa)", boxShadow: "0 20px 60px #173c2010" }} aria-hidden="true">
        <div className="grid h-36 w-36 place-items-center rounded-[2rem] text-white" style={{ background: "linear-gradient(145deg,#1b9a5c,#11633c)", boxShadow: "0 14px 35px #167d4930" }}><Zap size={66} strokeWidth={1.5} /></div>
      </div>
    </section>
    <footer className="border-t px-5 py-5 text-center text-xs sm:px-8 sm:text-left" style={{ borderColor: "var(--line)", color: "var(--muted)" }}>© {new Date().getFullYear()} D-ENERGY · DNS HOSTESS S.R.L.</footer>
  </main>;
}
