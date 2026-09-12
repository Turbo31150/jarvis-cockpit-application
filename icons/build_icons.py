#!/usr/bin/env python3
"""
build_icons.py — Générateur d'icônes Haute Définition (512x512)
pour les applications du Bureau JARVIS OS.
"""

import os
import subprocess
import tempfile

ICONS_DIR = "/home/turbo/jarvis/icons"
os.makedirs(ICONS_DIR, exist_ok=True)

# Définition des 6 icônes avec design SVG/HTML/CSS ultra-léché
ICONS = {
    "1_jarvis_cockpit_os": {
        "title": "COCKPIT OS",
        "border_color": "#00f0ff",
        "bg_gradient": "radial-gradient(circle at 50% 30%, #0d2847 0%, #061324 60%, #02070e 100%)",
        "glow_color": "rgba(0, 240, 255, 0.45)",
        "badge_bg": "rgba(0, 240, 255, 0.15)",
        "badge_border": "#00f0ff",
        "badge_text": "#00f0ff",
        "badge_label": "COCKPIT MASTER",
        "svg": """
        <!-- Arc Reactor / Holographic Master Core -->
        <circle cx="256" cy="220" r="130" fill="none" stroke="#00f0ff" stroke-width="3" stroke-dasharray="8 6" opacity="0.6"/>
        <circle cx="256" cy="220" r="115" fill="none" stroke="#38bdf8" stroke-width="4" opacity="0.8"/>
        
        <!-- Outer tick rings -->
        <g stroke="#00f0ff" stroke-width="3" opacity="0.7">
            <line x1="256" y1="80" x2="256" y2="100"/>
            <line x1="256" y1="340" x2="256" y2="360"/>
            <line x1="116" y1="220" x2="136" y2="220"/>
            <line x1="376" y1="220" x2="396" y2="220"/>
            <line x1="157" y1="121" x2="171" y2="135"/>
            <line x1="355" y1="319" x2="341" y2="305"/>
            <line x1="157" y1="319" x2="171" y2="305"/>
            <line x1="355" y1="121" x2="341" y2="135"/>
        </g>
        
        <!-- Segmented reactor ring -->
        <circle cx="256" cy="220" r="85" fill="#041226" stroke="#0ea5e9" stroke-width="8" stroke-dasharray="40 10"/>
        
        <!-- Energy triangles / turbine blades -->
        <polygon points="256,150 240,195 272,195" fill="#00f0ff" opacity="0.85"/>
        <polygon points="256,290 240,245 272,245" fill="#00f0ff" opacity="0.85"/>
        <polygon points="186,220 231,204 231,236" fill="#00f0ff" opacity="0.85"/>
        <polygon points="326,220 281,204 281,236" fill="#00f0ff" opacity="0.85"/>
        <polygon points="206,170 245,190 225,210" fill="#38bdf8" opacity="0.85"/>
        <polygon points="306,270 267,250 287,230" fill="#38bdf8" opacity="0.85"/>
        <polygon points="206,270 245,250 225,230" fill="#38bdf8" opacity="0.85"/>
        <polygon points="306,170 267,190 287,210" fill="#38bdf8" opacity="0.85"/>

        <!-- Glowing Central Core -->
        <circle cx="256" cy="220" r="45" fill="#08203e" stroke="#00f0ff" stroke-width="4"/>
        <circle cx="256" cy="220" r="30" fill="url(#coreGlow)" />
        <circle cx="256" cy="220" r="14" fill="#ffffff"/>
        
        <defs>
            <radialGradient id="coreGlow" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stop-color="#ffffff"/>
                <stop offset="40%" stop-color="#00f0ff"/>
                <stop offset="80%" stop-color="#0284c7"/>
                <stop offset="100%" stop-color="#0369a1"/>
            </radialGradient>
        </defs>
        """
    },
    
    "2_jarvis_web_cockpit": {
        "title": "WEB COCKPIT",
        "border_color": "#14b8a6",
        "bg_gradient": "radial-gradient(circle at 50% 30%, #0d2e38 0%, #06161c 60%, #02090c 100%)",
        "glow_color": "rgba(20, 184, 166, 0.45)",
        "badge_bg": "rgba(20, 184, 166, 0.15)",
        "badge_border": "#14b8a6",
        "badge_text": "#2dd4bf",
        "badge_label": "PORT :8600",
        "svg": """
        <!-- Quantum Web Globe & Network Sphere -->
        <circle cx="256" cy="220" r="125" fill="#041419" stroke="#14b8a6" stroke-width="4" opacity="0.7"/>
        
        <!-- Latitude lines -->
        <ellipse cx="256" cy="220" rx="125" ry="40" fill="none" stroke="#2dd4bf" stroke-width="3" stroke-dasharray="10 8" opacity="0.6"/>
        <ellipse cx="256" cy="220" rx="125" ry="85" fill="none" stroke="#2dd4bf" stroke-width="2.5" opacity="0.5"/>
        <line x1="131" y1="220" x2="381" y2="220" stroke="#2dd4bf" stroke-width="2" opacity="0.7"/>
        
        <!-- Longitude lines -->
        <ellipse cx="256" cy="220" rx="55" ry="125" fill="none" stroke="#2dd4bf" stroke-width="3" opacity="0.6"/>
        <line x1="256" y1="95" x2="256" y2="345" stroke="#2dd4bf" stroke-width="2" opacity="0.7"/>
        
        <!-- Orbital Node Ring -->
        <ellipse cx="256" cy="220" rx="155" ry="55" fill="none" stroke="#00f0ff" stroke-width="2.5" stroke-dasharray="6 8" transform="rotate(-25 256 220)" opacity="0.85"/>
        
        <!-- Orbital Satellites / Nodes -->
        <circle cx="120" cy="160" r="8" fill="#00f0ff" filter="drop-shadow(0 0 6px #00f0ff)"/>
        <circle cx="390" cy="280" r="8" fill="#00f0ff" filter="drop-shadow(0 0 6px #00f0ff)"/>
        <circle cx="280" cy="170" r="6" fill="#a7f3d0"/>
        
        <!-- Center Cyber HUD Shield -->
        <polygon points="256,170 295,190 295,245 256,270 217,245 217,190" fill="#082329" stroke="#5eead4" stroke-width="4"/>
        <text x="256" y="228" font-family="'JetBrains Mono', monospace" font-size="26" font-weight="900" fill="#ffffff" text-anchor="middle">WEB</text>
        <circle cx="256" cy="250" r="4" fill="#00f0ff"/>
        """
    },

    "3_jarvis_ttx_multiplexeur": {
        "title": "TTX MULTIPLEXEUR",
        "border_color": "#00ff88",
        "bg_gradient": "radial-gradient(circle at 50% 30%, #072a1a 0%, #03140c 60%, #010704 100%)",
        "glow_color": "rgba(0, 255, 136, 0.45)",
        "badge_bg": "rgba(0, 255, 136, 0.15)",
        "badge_border": "#00ff88",
        "badge_text": "#00ff88",
        "badge_label": "14 ÉCRANS TMUX",
        "svg": """
        <!-- Glass Terminal Window Shell -->
        <rect x="116" y="90" width="280" height="230" rx="16" fill="#041209" stroke="#00ff88" stroke-width="4"/>
        
        <!-- Title bar -->
        <rect x="116" y="90" width="280" height="34" rx="16" fill="#062211"/>
        <rect x="116" y="110" width="280" height="14" fill="#062211"/>
        <line x1="116" y1="124" x2="396" y2="124" stroke="#00ff88" stroke-width="2" opacity="0.6"/>
        <circle cx="138" cy="107" r="5" fill="#ef4444"/>
        <circle cx="154" cy="107" r="5" fill="#eab308"/>
        <circle cx="170" cy="107" r="5" fill="#22c55e"/>
        <text x="270" y="112" font-family="'JetBrains Mono', monospace" font-size="12" fill="#86efac" text-anchor="middle" font-weight="700">JARVIS-TTX : 14 WINS</text>

        <!-- 14-Screen Matrix Multiplexer Grid (Pane layout) -->
        <!-- Pane 1: Main HUD -->
        <rect x="132" y="136" width="118" height="68" rx="6" fill="#072010" stroke="#10b981" stroke-width="2"/>
        <!-- Pane 2: Top Right -->
        <rect x="258" y="136" width="122" height="68" rx="6" fill="#072010" stroke="#10b981" stroke-width="2"/>
        <!-- Bottom Row (Panes 3, 4, 5) -->
        <rect x="132" y="212" width="76" height="52" rx="6" fill="#072010" stroke="#10b981" stroke-width="2"/>
        <rect x="216" y="212" width="78" height="52" rx="6" fill="#072010" stroke="#10b981" stroke-width="2"/>
        <rect x="302" y="212" width="78" height="52" rx="6" fill="#072010" stroke="#10b981" stroke-width="2"/>

        <!-- Multiplexer Terminal Prompt Indicator -->
        <text x="144" y="165" font-family="'JetBrains Mono', monospace" font-size="20" font-weight="900" fill="#00ff88">&gt;_</text>
        <text x="174" y="165" font-family="'JetBrains Mono', monospace" font-size="15" font-weight="700" fill="#ffffff">HUD</text>
        <text x="144" y="188" font-family="'JetBrains Mono', monospace" font-size="11" fill="#4ade80">0:Master*</text>

        <text x="270" y="165" font-family="'JetBrains Mono', monospace" font-size="14" font-weight="700" fill="#67e8f9">1:Claude</text>
        <text x="270" y="188" font-family="'JetBrains Mono', monospace" font-size="11" fill="#4ade80">2:Table</text>

        <text x="142" y="242" font-family="'JetBrains Mono', monospace" font-size="12" fill="#00ff88" font-weight="bold">#3</text>
        <text x="226" y="242" font-family="'JetBrains Mono', monospace" font-size="12" fill="#00ff88" font-weight="bold">#4</text>
        <text x="312" y="242" font-family="'JetBrains Mono', monospace" font-size="12" fill="#00ff88" font-weight="bold">#5..13</text>

        <!-- Activity status LED bar -->
        <rect x="132" y="278" width="248" height="26" rx="6" fill="#031006" stroke="#00ff88" stroke-width="1.5"/>
        <circle cx="150" cy="291" r="5" fill="#00ff88" filter="drop-shadow(0 0 5px #00ff88)"/>
        <text x="165" y="295" font-family="'JetBrains Mono', monospace" font-size="11" font-weight="bold" fill="#86efac">14/14 TERMINAUX ACTIFS</text>
        """
    },

    "4_jarvis_table_ronde": {
        "title": "TABLE RONDE",
        "border_color": "#c084fc",
        "bg_gradient": "radial-gradient(circle at 50% 30%, #351457 0%, #1a082e 60%, #0b0214 100%)",
        "glow_color": "rgba(192, 132, 252, 0.45)",
        "badge_bg": "rgba(192, 132, 252, 0.15)",
        "badge_border": "#c084fc",
        "badge_text": "#e9d5ff",
        "badge_label": "48 EXPERTS IA",
        "svg": """
        <!-- Grand Sovereign Council Round Table & Constellation -->
        <circle cx="256" cy="215" r="128" fill="none" stroke="#a855f7" stroke-width="3" stroke-dasharray="8 6" opacity="0.6"/>
        <circle cx="256" cy="215" r="110" fill="#120521" stroke="#c084fc" stroke-width="4"/>
        
        <!-- Table surface with mahogany/violet luster -->
        <circle cx="256" cy="215" r="80" fill="#230a3d" stroke="#e879f9" stroke-width="3"/>
        
        <!-- 7 Sovereign Agent Nodes on the Perimeter -->
        <!-- Center connecting laser beams -->
        <g stroke="#f59e0b" stroke-width="2" opacity="0.65">
            <line x1="256" y1="215" x2="256" y2="105"/>
            <line x1="256" y1="215" x2="345" y2="148"/>
            <line x1="256" y1="215" x2="362" y2="252"/>
            <line x1="256" y1="215" x2="298" y2="320"/>
            <line x1="256" y1="215" x2="214" y2="320"/>
            <line x1="256" y1="215" x2="150" y2="252"/>
            <line x1="256" y1="215" x2="167" y2="148"/>
        </g>

        <!-- 7 Agent Nodes (Distinct Expert Colors) -->
        <circle cx="256" cy="105" r="14" fill="#34d399" stroke="#ffffff" stroke-width="2.5" filter="drop-shadow(0 0 6px #34d399)"/>
        <circle cx="345" cy="148" r="14" fill="#fbbf24" stroke="#ffffff" stroke-width="2.5" filter="drop-shadow(0 0 6px #fbbf24)"/>
        <circle cx="362" cy="252" r="14" fill="#38bdf8" stroke="#ffffff" stroke-width="2.5" filter="drop-shadow(0 0 6px #38bdf8)"/>
        <circle cx="298" cy="320" r="14" fill="#22d3ee" stroke="#ffffff" stroke-width="2.5" filter="drop-shadow(0 0 6px #22d3ee)"/>
        <circle cx="214" cy="320" r="14" fill="#c084fc" stroke="#ffffff" stroke-width="2.5" filter="drop-shadow(0 0 6px #c084fc)"/>
        <circle cx="150" cy="252" r="14" fill="#2dd4bf" stroke="#ffffff" stroke-width="2.5" filter="drop-shadow(0 0 6px #2dd4bf)"/>
        <circle cx="167" cy="148" r="14" fill="#fb923c" stroke="#ffffff" stroke-width="2.5" filter="drop-shadow(0 0 6px #fb923c)"/>

        <!-- Central Supreme Arbitrator Dais & Scales / Crown -->
        <circle cx="256" cy="215" r="36" fill="#3b0764" stroke="#fbbf24" stroke-width="4" filter="drop-shadow(0 0 10px #fbbf24)"/>
        <text x="256" y="226" font-size="34" text-anchor="middle">🏛️</text>
        """
    },

    "5_jarvis_cluster_5_gpu": {
        "title": "CLUSTER 5-GPU",
        "border_color": "#76b900",
        "bg_gradient": "radial-gradient(circle at 50% 30%, #1a330a 0%, #0d1b04 60%, #040801 100%)",
        "glow_color": "rgba(118, 185, 0, 0.45)",
        "badge_bg": "rgba(118, 185, 0, 0.15)",
        "badge_border": "#76b900",
        "badge_text": "#a3e635",
        "badge_label": "CUDA 12 · 5-GPU",
        "svg": """
        <!-- NVIDIA Silicon Die & 5-GPU Accelerator Architecture -->
        <!-- Chip Die Frame -->
        <rect x="116" y="90" width="280" height="230" rx="20" fill="#0b1706" stroke="#76b900" stroke-width="4"/>
        
        <!-- Golden PCB Edge Connectors (PCIe Pins) -->
        <g fill="#eab308">
            <rect x="140" y="320" width="12" height="12" rx="2"/>
            <rect x="165" y="320" width="12" height="12" rx="2"/>
            <rect x="190" y="320" width="12" height="12" rx="2"/>
            <rect x="215" y="320" width="12" height="12" rx="2"/>
            <rect x="240" y="320" width="12" height="12" rx="2"/>
            <rect x="265" y="320" width="12" height="12" rx="2"/>
            <rect x="290" y="320" width="12" height="12" rx="2"/>
            <rect x="315" y="320" width="12" height="12" rx="2"/>
            <rect x="340" y="320" width="12" height="12" rx="2"/>
            <rect x="360" y="320" width="12" height="12" rx="2"/>
        </g>
        
        <!-- 5 Parallel GPU Core Processors -->
        <!-- GPU 0 -->
        <rect x="132" y="115" width="42" height="120" rx="8" fill="#14290a" stroke="#76b900" stroke-width="2.5"/>
        <text x="153" y="145" font-family="'JetBrains Mono', monospace" font-size="12" font-weight="bold" fill="#a3e635" text-anchor="middle">GPU</text>
        <text x="153" y="170" font-family="'JetBrains Mono', monospace" font-size="20" font-weight="900" fill="#ffffff" text-anchor="middle">0</text>
        <circle cx="153" cy="205" r="5" fill="#76b900"/>

        <!-- GPU 1 -->
        <rect x="184" y="115" width="42" height="120" rx="8" fill="#14290a" stroke="#76b900" stroke-width="2.5"/>
        <text x="205" y="145" font-family="'JetBrains Mono', monospace" font-size="12" font-weight="bold" fill="#a3e635" text-anchor="middle">GPU</text>
        <text x="205" y="170" font-family="'JetBrains Mono', monospace" font-size="20" font-weight="900" fill="#ffffff" text-anchor="middle">1</text>
        <circle cx="205" cy="205" r="5" fill="#76b900"/>

        <!-- GPU 2 (Center Master) -->
        <rect x="236" y="110" width="42" height="130" rx="8" fill="#1f3f10" stroke="#a3e635" stroke-width="3" filter="drop-shadow(0 0 6px #76b900)"/>
        <text x="257" y="145" font-family="'JetBrains Mono', monospace" font-size="12" font-weight="bold" fill="#ffffff" text-anchor="middle">GPU</text>
        <text x="257" y="172" font-family="'JetBrains Mono', monospace" font-size="22" font-weight="900" fill="#a3e635" text-anchor="middle">2</text>
        <circle cx="257" cy="210" r="6" fill="#00f0ff"/>

        <!-- GPU 3 -->
        <rect x="288" y="115" width="42" height="120" rx="8" fill="#14290a" stroke="#76b900" stroke-width="2.5"/>
        <text x="309" y="145" font-family="'JetBrains Mono', monospace" font-size="12" font-weight="bold" fill="#a3e635" text-anchor="middle">GPU</text>
        <text x="309" y="170" font-family="'JetBrains Mono', monospace" font-size="20" font-weight="900" fill="#ffffff" text-anchor="middle">3</text>
        <circle cx="309" cy="205" r="5" fill="#76b900"/>

        <!-- GPU 4 -->
        <rect x="340" y="115" width="42" height="120" rx="8" fill="#14290a" stroke="#76b900" stroke-width="2.5"/>
        <text x="361" y="145" font-family="'JetBrains Mono', monospace" font-size="12" font-weight="bold" fill="#a3e635" text-anchor="middle">GPU</text>
        <text x="361" y="170" font-family="'JetBrains Mono', monospace" font-size="20" font-weight="900" fill="#ffffff" text-anchor="middle">4</text>
        <circle cx="361" cy="205" r="5" fill="#76b900"/>

        <!-- High-Speed NVLink / P2P Interconnect bus line -->
        <line x1="140" y1="260" x2="370" y2="260" stroke="#00f0ff" stroke-width="3"/>
        <text x="256" y="292" font-family="'JetBrains Mono', monospace" font-size="13" font-weight="900" fill="#00f0ff" text-anchor="middle">NVLINK · P2P TOPO · UVM</text>
        """
    },

    "6_jarvis_sauvegarde_disque": {
        "title": "SAUVEGARDE IMAGE",
        "border_color": "#38bdf8",
        "bg_gradient": "radial-gradient(circle at 50% 30%, #0e2a4a 0%, #071629 60%, #02070f 100%)",
        "glow_color": "rgba(56, 189, 248, 0.45)",
        "badge_bg": "rgba(56, 189, 248, 0.15)",
        "badge_border": "#38bdf8",
        "badge_text": "#7dd3fc",
        "badge_label": "ISO · VHDX · M1",
        "svg": """
        <!-- Quantum Optical Platter & Armored Vault -->
        <!-- Outer Vault Armor -->
        <polygon points="256,90 380,140 380,265 256,335 132,265 132,140" fill="#07182c" stroke="#38bdf8" stroke-width="4"/>
        
        <!-- Optical Storage Platter -->
        <circle cx="256" cy="210" r="85" fill="#0a233d" stroke="#60a5fa" stroke-width="3"/>
        
        <!-- Laser tracks / rainbow diffraction -->
        <circle cx="256" cy="210" r="68" fill="none" stroke="#38bdf8" stroke-width="2" stroke-dasharray="14 8" opacity="0.8"/>
        <circle cx="256" cy="210" r="50" fill="none" stroke="#93c5fd" stroke-width="2" stroke-dasharray="8 6" opacity="0.8"/>
        
        <!-- Platter Spindle / Center Hole -->
        <circle cx="256" cy="210" r="26" fill="#030b14" stroke="#38bdf8" stroke-width="4"/>
        <circle cx="256" cy="210" r="10" fill="#ffffff" filter="drop-shadow(0 0 6px #ffffff)"/>

        <!-- Armored Lock / Verified Check Shield -->
        <polygon points="256,120 285,135 285,165 256,180 227,165 227,135" fill="#0369a1" stroke="#38bdf8" stroke-width="2"/>
        <path d="M246,148 L253,155 L268,140" fill="none" stroke="#ffffff" stroke-width="3.5" stroke-linecap="round"/>
        
        <!-- Format Labels -->
        <text x="185" y="270" font-family="'JetBrains Mono', monospace" font-size="12" font-weight="900" fill="#38bdf8">.ISO</text>
        <text x="325" y="270" font-family="'JetBrains Mono', monospace" font-size="12" font-weight="900" fill="#38bdf8" text-anchor="end">.VHDX</text>
        <text x="256" y="295" font-family="'JetBrains Mono', monospace" font-size="10" font-weight="bold" fill="#93c5fd" text-anchor="middle">SHA-256 SOUVERAIN</text>
        """
    },

    "claude_desktop": {
        "title": "CLAUDE DESKTOP",
        "border_color": "#f59e0b",
        "bg_gradient": "radial-gradient(circle at 50% 30%, #3d1f0b 0%, #1f0e04 60%, #0a0401 100%)",
        "glow_color": "rgba(245, 158, 11, 0.45)",
        "badge_bg": "rgba(245, 158, 11, 0.15)",
        "badge_border": "#f59e0b",
        "badge_text": "#fbbf24",
        "badge_label": "ANTHROPIC AI",
        "svg": """
        <!-- Anthropic Claude Spark / Neural Geometry -->
        <circle cx="256" cy="215" r="125" fill="none" stroke="#d97706" stroke-width="2.5" stroke-dasharray="10 8" opacity="0.6"/>
        <circle cx="256" cy="215" r="105" fill="#140802" stroke="#f59e0b" stroke-width="4"/>
        
        <!-- Radiant Star Rays -->
        <g stroke="#f59e0b" stroke-width="12" stroke-linecap="round">
            <line x1="256" y1="135" x2="256" y2="295"/>
            <line x1="176" y1="215" x2="336" y2="215"/>
            <line x1="199" y1="158" x2="313" y2="272"/>
            <line x1="199" y1="272" x2="313" y2="158"/>
        </g>
        
        <!-- Center Neural Core -->
        <circle cx="256" cy="215" r="42" fill="#78350f" stroke="#fbbf24" stroke-width="4"/>
        <circle cx="256" cy="215" r="22" fill="#fef3c7" filter="drop-shadow(0 0 10px #f59e0b)"/>
        """
    },

    "antigravity_ide": {
        "title": "ANTIGRAVITY",
        "border_color": "#a855f7",
        "bg_gradient": "radial-gradient(circle at 50% 30%, #2b0e4f 0%, #150629 60%, #080212 100%)",
        "glow_color": "rgba(168, 85, 247, 0.45)",
        "badge_bg": "rgba(168, 85, 247, 0.15)",
        "badge_border": "#a855f7",
        "badge_text": "#d8b4fe",
        "badge_label": "GOOGLE AGY",
        "svg": """
        <!-- Antigravity Cosmic Levitation Rings -->
        <circle cx="256" cy="215" r="130" fill="none" stroke="#7e22ce" stroke-width="2.5" stroke-dasharray="8 6" opacity="0.6"/>
        <ellipse cx="256" cy="215" rx="125" ry="50" fill="none" stroke="#c084fc" stroke-width="4" transform="rotate(-30 256 215)"/>
        <ellipse cx="256" cy="215" rx="125" ry="50" fill="none" stroke="#60a5fa" stroke-width="4" transform="rotate(30 256 215)"/>
        
        <!-- Levitating Diamond Prism -->
        <polygon points="256,135 316,215 256,295 196,215" fill="#3b0764" stroke="#a855f7" stroke-width="4" filter="drop-shadow(0 0 12px #a855f7)"/>
        <polygon points="256,165 296,215 256,265 216,215" fill="#e9d5ff" stroke="#ffffff" stroke-width="2"/>
        <circle cx="256" cy="215" r="10" fill="#ffffff" filter="drop-shadow(0 0 8px #ffffff)"/>
        """
    },

    "google_chrome": {
        "title": "GOOGLE CHROME",
        "border_color": "#3b82f6",
        "bg_gradient": "radial-gradient(circle at 50% 30%, #0e2744 0%, #071526 60%, #02070f 100%)",
        "glow_color": "rgba(59, 130, 246, 0.45)",
        "badge_bg": "rgba(59, 130, 246, 0.15)",
        "badge_border": "#3b82f6",
        "badge_text": "#93c5fd",
        "badge_label": "NAVIGATEUR",
        "svg": """
        <!-- Cyber Chrome Aperture -->
        <circle cx="256" cy="215" r="125" fill="#06162a" stroke="#3b82f6" stroke-width="4"/>
        
        <!-- Tri-sector Aperture Rings (Red, Green, Yellow in cyber aesthetic) -->
        <path d="M 256 90 A 125 125 0 0 1 364 277 L 295 240 A 50 50 0 0 0 256 165 Z" fill="#ef4444" opacity="0.85"/>
        <path d="M 364 277 A 125 125 0 0 1 148 277 L 183 215 A 50 50 0 0 0 295 240 Z" fill="#22c55e" opacity="0.85"/>
        <path d="M 148 277 A 125 125 0 0 1 256 90 L 256 165 A 50 50 0 0 0 183 215 Z" fill="#eab308" opacity="0.85"/>
        
        <!-- Center Blue Core -->
        <circle cx="256" cy="215" r="50" fill="#1d4ed8" stroke="#ffffff" stroke-width="5"/>
        <circle cx="256" cy="215" r="22" fill="#60a5fa" filter="drop-shadow(0 0 8px #ffffff)"/>
        """
    },

    "terminal_remi": {
        "title": "RÉMI DIRECT",
        "border_color": "#06b6d4",
        "bg_gradient": "radial-gradient(circle at 50% 30%, #083344 0%, #041a24 60%, #020b10 100%)",
        "glow_color": "rgba(6, 182, 212, 0.45)",
        "badge_bg": "rgba(6, 182, 212, 0.15)",
        "badge_border": "#06b6d4",
        "badge_text": "#67e8f9",
        "badge_label": "TAILSCALE SSH",
        "svg": """
        <!-- Direct Terminal to Rémi (100.113.121.61) -->
        <rect x="116" y="95" width="280" height="220" rx="16" fill="#03151e" stroke="#06b6d4" stroke-width="4"/>
        <rect x="116" y="95" width="280" height="32" rx="16" fill="#082b3a"/>
        <circle cx="138" cy="111" r="5" fill="#ef4444"/>
        <circle cx="154" cy="111" r="5" fill="#eab308"/>
        <circle cx="170" cy="111" r="5" fill="#22c55e"/>
        <text x="256" y="116" font-family="'JetBrains Mono', monospace" font-size="11" font-weight="bold" fill="#67e8f9" text-anchor="middle">rem-linux · 100.113.121.61</text>
        
        <text x="140" y="165" font-family="'JetBrains Mono', monospace" font-size="20" font-weight="900" fill="#00f0ff">&gt; ssh rem</text>
        <text x="140" y="195" font-family="'JetBrains Mono', monospace" font-size="13" font-weight="bold" fill="#4ade80">● Tunnel WireGuard ACTIF</text>
        <text x="140" y="220" font-family="'JetBrains Mono', monospace" font-size="12" fill="#94a3b8">Hôte: rem-linux (M1 / Rémi)</text>
        <text x="140" y="245" font-family="'JetBrains Mono', monospace" font-size="12" fill="#94a3b8">Utilisateur: rempc / root</text>
        <rect x="135" y="265" width="242" height="32" rx="6" fill="#05202c" stroke="#06b6d4" stroke-width="1.5"/>
        <text x="256" y="286" font-family="'JetBrains Mono', monospace" font-size="12" font-weight="bold" fill="#38bdf8" text-anchor="middle">⚡ SESSION DIRECTE SOUVERAINE</text>
        """
    },

    "terminal_m1": {
        "title": "M1 CLUSTER",
        "border_color": "#10b981",
        "bg_gradient": "radial-gradient(circle at 50% 30%, #063826 0%, #031c13 60%, #010c08 100%)",
        "glow_color": "rgba(16, 185, 129, 0.45)",
        "badge_bg": "rgba(16, 185, 129, 0.15)",
        "badge_border": "#10b981",
        "badge_text": "#6ee7b7",
        "badge_label": "SSH M1 MASTER",
        "svg": """
        <!-- M1 Master Server Console -->
        <rect x="116" y="95" width="280" height="220" rx="16" fill="#02170f" stroke="#10b981" stroke-width="4"/>
        <rect x="116" y="95" width="280" height="32" rx="16" fill="#062e1e"/>
        <circle cx="138" cy="111" r="5" fill="#ef4444"/>
        <circle cx="154" cy="111" r="5" fill="#eab308"/>
        <circle cx="170" cy="111" r="5" fill="#22c55e"/>
        <text x="256" y="116" font-family="'JetBrains Mono', monospace" font-size="11" font-weight="bold" fill="#a7f3d0" text-anchor="middle">jarvis-m1 · 192.168.1.85</text>
        
        <text x="140" y="165" font-family="'JetBrains Mono', monospace" font-size="20" font-weight="900" fill="#10b981">&gt; ssh m1</text>
        <text x="140" y="195" font-family="'JetBrains Mono', monospace" font-size="13" font-weight="bold" fill="#34d399">● Nœud M1 SSD 1To Master</text>
        <text x="140" y="220" font-family="'JetBrains Mono', monospace" font-size="12" fill="#94a3b8">Réseau: 192.168.1.85 / eth</text>
        <text x="140" y="245" font-family="'JetBrains Mono', monospace" font-size="12" fill="#94a3b8">Bridge: m6 direct / m4 hub</text>
        <rect x="135" y="265" width="242" height="32" rx="6" fill="#032115" stroke="#10b981" stroke-width="1.5"/>
        <text x="256" y="286" font-family="'JetBrains Mono', monospace" font-size="12" font-weight="bold" fill="#6ee7b7" text-anchor="middle">🖥 CONSOLE MAÎTRESSE M1</text>
        """
    },

    "chrome_franck": {
        "title": "CHROME FRANCK",
        "border_color": "#38bdf8",
        "bg_gradient": "radial-gradient(circle at 50% 30%, #0c2b4a 0%, #061729 60%, #020912 100%)",
        "glow_color": "rgba(56, 189, 248, 0.45)",
        "badge_bg": "rgba(56, 189, 248, 0.15)",
        "badge_border": "#38bdf8",
        "badge_text": "#7dd3fc",
        "badge_label": "PROFIL PRINCIPAL",
        "svg": """
        <circle cx="256" cy="205" r="95" fill="#071b30" stroke="#38bdf8" stroke-width="4"/>
        <text x="256" y="200" font-size="52" text-anchor="middle">👤</text>
        <text x="256" y="235" font-family="'JetBrains Mono', monospace" font-size="16" font-weight="900" fill="#ffffff" text-anchor="middle">FRANCK</text>
        <text x="256" y="255" font-family="'JetBrains Mono', monospace" font-size="11" fill="#7dd3fc" text-anchor="middle">franckdelmas00@gmail.com</text>
        """
    },

    "chrome_mining": {
        "title": "CHROME MINING",
        "border_color": "#f59e0b",
        "bg_gradient": "radial-gradient(circle at 50% 30%, #3d2309 0%, #1e1104 60%, #0c0701 100%)",
        "glow_color": "rgba(245, 158, 11, 0.45)",
        "badge_bg": "rgba(245, 158, 11, 0.15)",
        "badge_border": "#f59e0b",
        "badge_text": "#fbbf24",
        "badge_label": "MINING EXPERT",
        "svg": """
        <circle cx="256" cy="205" r="95" fill="#261404" stroke="#f59e0b" stroke-width="4"/>
        <text x="256" y="200" font-size="52" text-anchor="middle">⛏️</text>
        <text x="256" y="235" font-family="'JetBrains Mono', monospace" font-size="16" font-weight="900" fill="#ffffff" text-anchor="middle">MINING EXPERT</text>
        <text x="256" y="255" font-family="'JetBrains Mono', monospace" font-size="11" fill="#fbbf24" text-anchor="middle">miningexpert31@gmail.com</text>
        """
    },

    "chrome_claire": {
        "title": "CHROME CLAIRE",
        "border_color": "#ec4899",
        "bg_gradient": "radial-gradient(circle at 50% 30%, #3d0d26 0%, #200613 60%, #0e0208 100%)",
        "glow_color": "rgba(236, 72, 153, 0.45)",
        "badge_bg": "rgba(236, 72, 153, 0.15)",
        "badge_border": "#ec4899",
        "badge_text": "#f472b6",
        "badge_label": "PROFIL CLAIRE",
        "svg": """
        <circle cx="256" cy="205" r="95" fill="#240716" stroke="#ec4899" stroke-width="4"/>
        <text x="256" y="200" font-size="52" text-anchor="middle">🌸</text>
        <text x="256" y="235" font-family="'JetBrains Mono', monospace" font-size="16" font-weight="900" fill="#ffffff" text-anchor="middle">CLAIRE</text>
        <text x="256" y="255" font-family="'JetBrains Mono', monospace" font-size="11" fill="#f472b6" text-anchor="middle">claire.dms64@gmail.com</text>
        """
    },

    "chrome_remi": {
        "title": "CHROME RÉMI",
        "border_color": "#10b981",
        "bg_gradient": "radial-gradient(circle at 50% 30%, #063622 0%, #031b11 60%, #010a06 100%)",
        "glow_color": "rgba(16, 185, 129, 0.45)",
        "badge_bg": "rgba(16, 185, 129, 0.15)",
        "badge_border": "#10b981",
        "badge_text": "#6ee7b7",
        "badge_label": "PROFIL RÉMI",
        "svg": """
        <circle cx="256" cy="205" r="95" fill="#031f13" stroke="#10b981" stroke-width="4"/>
        <text x="256" y="200" font-size="52" text-anchor="middle">🛡️</text>
        <text x="256" y="235" font-family="'JetBrains Mono', monospace" font-size="16" font-weight="900" fill="#ffffff" text-anchor="middle">RÉMI</text>
        <text x="256" y="255" font-family="'JetBrains Mono', monospace" font-size="11" fill="#6ee7b7" text-anchor="middle">remten341@gmail.com</text>
        """
    },

    "chrome_logs": {
        "title": "LOGS CHROME CDP",
        "border_color": "#f97316",
        "bg_gradient": "radial-gradient(circle at 50% 30%, #381a07 0%, #1c0c03 60%, #0a0401 100%)",
        "glow_color": "rgba(249, 115, 22, 0.45)",
        "badge_bg": "rgba(249, 115, 22, 0.15)",
        "badge_border": "#f97316",
        "badge_text": "#fb923c",
        "badge_label": "CDP :9222 DEBUG",
        "svg": """
        <rect x="116" y="95" width="280" height="220" rx="16" fill="#140902" stroke="#f97316" stroke-width="4"/>
        <rect x="116" y="95" width="280" height="32" rx="16" fill="#2d1305"/>
        <circle cx="138" cy="111" r="5" fill="#ef4444"/>
        <circle cx="154" cy="111" r="5" fill="#eab308"/>
        <circle cx="170" cy="111" r="5" fill="#22c55e"/>
        <text x="256" y="116" font-family="'JetBrains Mono', monospace" font-size="11" font-weight="bold" fill="#fdba74" text-anchor="middle">Chrome Remote Debugging :9222</text>
        <text x="140" y="165" font-family="'JetBrains Mono', monospace" font-size="18" font-weight="900" fill="#f97316">&gt; journalctl -u chrome-cdp</text>
        <text x="140" y="195" font-family="'JetBrains Mono', monospace" font-size="12" fill="#fed7aa">[CDP] Remote origins: *</text>
        <text x="140" y="215" font-family="'JetBrains Mono', monospace" font-size="12" fill="#fed7aa">[CDP] WebSocket devtools active</text>
        <text x="140" y="235" font-family="'JetBrains Mono', monospace" font-size="12" fill="#fed7aa">[CDP] Automation session open</text>
        <rect x="135" y="260" width="242" height="34" rx="6" fill="#200d03" stroke="#f97316" stroke-width="1.5"/>
        <text x="256" y="282" font-family="'JetBrains Mono', monospace" font-size="12" font-weight="bold" fill="#fb923c" text-anchor="middle">🔍 SURVEILLANCE &amp; LOGS LIVE</text>
        """
    },

    "anydesk": {
        "title": "ANYDESK",
        "border_color": "#ef4444",
        "bg_gradient": "radial-gradient(circle at 50% 30%, #3d0c0c 0%, #1f0505 60%, #0a0101 100%)",
        "glow_color": "rgba(239, 68, 68, 0.45)",
        "badge_bg": "rgba(239, 68, 68, 0.15)",
        "badge_border": "#ef4444",
        "badge_text": "#fca5a5",
        "badge_label": "BUREAU DISTANT",
        "svg": """
        <!-- AnyDesk Dual Screen / Remote Interconnect -->
        <rect x="136" y="125" width="160" height="110" rx="10" fill="#170404" stroke="#ef4444" stroke-width="3.5"/>
        <rect x="216" y="175" width="160" height="110" rx="10" fill="#260808" stroke="#f87171" stroke-width="3.5"/>
        <line x1="216" y1="180" x2="296" y2="235" stroke="#ffffff" stroke-width="3"/>
        <polygon points="256,190 270,180 265,195" fill="#ffffff"/>
        <circle cx="216" cy="180" r="6" fill="#ef4444"/>
        <circle cx="296" cy="235" r="6" fill="#22c55e"/>
        <text x="296" y="220" font-family="'JetBrains Mono', monospace" font-size="14" font-weight="900" fill="#ffffff" text-anchor="middle">REMOTE</text>
        """
    }
}

def render_icon(key, conf):
    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@700;800;900&family=Inter:wght@700;800;900&display=swap');

* {{ box-sizing: border-box; }}
body {{
    margin: 0;
    padding: 0;
    width: 512px;
    height: 512px;
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
}}

.squircle {{
    width: 480px;
    height: 480px;
    border-radius: 110px;
    background: {conf['bg_gradient']};
    border: 4px solid {conf['border_color']};
    box-shadow: 0 0 45px {conf['glow_color']}, inset 0 0 35px rgba(0, 0, 0, 0.7);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: space-between;
    position: relative;
    padding: 24px 20px 28px 20px;
    user-select: none;
}}

.svg-container {{
    position: absolute;
    top: 0;
    left: 0;
    width: 512px;
    height: 512px;
    pointer-events: none;
}}

.top-brand {{
    font-family: 'Inter', sans-serif;
    font-size: 16px;
    font-weight: 900;
    letter-spacing: 3px;
    color: rgba(255, 255, 255, 0.85);
    text-transform: uppercase;
    z-index: 10;
    text-shadow: 0 2px 8px rgba(0,0,0,0.8);
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 10px;
}}

.brand-dot {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: {conf['border_color']};
    box-shadow: 0 0 8px {conf['border_color']};
}}

.bottom-badge {{
    z-index: 10;
    background: {conf['badge_bg']};
    border: 2px solid {conf['badge_border']};
    border-radius: 30px;
    padding: 7px 22px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 15px;
    font-weight: 800;
    letter-spacing: 1.5px;
    color: {conf['badge_text']};
    box-shadow: 0 0 16px {conf['glow_color']};
    text-shadow: 0 0 10px {conf['glow_color']};
    margin-bottom: 8px;
}}
</style>
</head>
<body>
<div class="squircle">
    <div class="top-brand">
        <span class="brand-dot"></span>
        <span>{conf['title']}</span>
        <span class="brand-dot"></span>
    </div>
    
    <svg class="svg-container" viewBox="0 0 512 512">
        {conf['svg']}
    </svg>

    <div class="bottom-badge">{conf['badge_label']}</div>
</div>
</body>
</html>
"""
    tmp_html = f"/tmp/{key}.html"
    out_png = os.path.join(ICONS_DIR, f"{key}.png")
    out_svg = os.path.join(ICONS_DIR, f"{key}.svg")

    with open(tmp_html, "w", encoding="utf-8") as f:
        f.write(html_content)

    # Sauvegarde également du SVG autonome
    with open(out_svg, "w", encoding="utf-8") as f:
        f.write(f"""<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <rect x="16" y="16" width="480" height="480" rx="110" fill="{conf['border_color']}" fill-opacity="0.1" stroke="{conf['border_color']}" stroke-width="4"/>
  {conf['svg']}
</svg>""")

    print(f"Rendering {key} -> {out_png}...")
    cmd = [
        "google-chrome",
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        f"--user-data-dir=/tmp/chrome_render_{key}",
        f"--screenshot={out_png}",
        "--window-size=512,512",
        "--default-background-color=00000000",
        tmp_html
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    # Copie dans le thème hicolor local
    hicolor_dest = os.path.expanduser(f"~/.local/share/icons/hicolor/512x512/apps/{key}.png")
    subprocess.run(["cp", out_png, hicolor_dest], check=True)
    print(f"✓ Created {out_png} & {hicolor_dest}")

if __name__ == "__main__":
    for k, v in ICONS.items():
        render_icon(k, v)
    print("\nAll 6 high-definition icons rendered successfully!")
