#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB 15 : BUREAU GNOME & VERROUS
Pilotage tracé de la barre des tâches, des icônes, des verrous et des écrans.
Même moteur que la façade web :8600 — core/bureau_engine.py.
"""

import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QTabWidget, QTextEdit, QComboBox, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from core.bureau_engine import get_bureau_etat, run_bureau_action, lire_traces

COULEUR_VERDICT = {
    "APPLIQUE": "#4ade80", "CONSTAT": "#38bdf8",
    "ECHEC": "#f87171", "HORS-LOGICIEL": "#fbbf24",
}


class BureauWorker(QThread):
    """Les actions passent par gnome-extensions (2-4 s) : jamais sur le thread GUI."""
    finished_signal = pyqtSignal(dict)

    def __init__(self, action, params=None):
        super().__init__()
        self.action = action
        self.params = params or {}

    def run(self):
        self.finished_signal.emit(run_bureau_action(self.action, self.params))


class TabBureau(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None          # référence gardée : sinon le GC le ramasse en vol
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        top_h = QHBoxLayout()
        lbl = QLabel("🖥 PILOTAGE TRACÉ DU BUREAU GNOME — BARRE · ICÔNES · VERROUS · ÉCRANS")
        lbl.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #fb7185;")
        top_h.addWidget(lbl)
        top_h.addStretch()

        self.lbl_conforme = QLabel("…")
        self.lbl_conforme.setFont(QFont("Ubuntu", 10, QFont.Weight.Bold))
        top_h.addWidget(self.lbl_conforme)

        btn_refresh = QPushButton("🔄 Constat")
        btn_refresh.clicked.connect(self.refresh_bureau)
        top_h.addWidget(btn_refresh)
        layout.addLayout(top_h)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Gauche : les 4 domaines ──
        gauche = QWidget()
        gl = QVBoxLayout(gauche)
        gl.setContentsMargins(0, 0, 0, 0)
        self.onglets = QTabWidget()

        # BARRE
        w_barre = QWidget(); l_barre = QVBoxLayout(w_barre)
        pos_h = QHBoxLayout()
        pos_h.addWidget(QLabel("Position :"))
        self.combo_pos = QComboBox()
        self.combo_pos.addItems(["BOTTOM", "TOP", "LEFT", "RIGHT"])
        pos_h.addWidget(self.combo_pos)
        b_pos = QPushButton("Appliquer")
        b_pos.setProperty("class", "green")
        b_pos.clicked.connect(lambda: self.lancer_action(
            "barre.set", {"cle": "dock-position", "valeur": self.combo_pos.currentText()}))
        pos_h.addWidget(b_pos)
        b_rel = QPushButton("♻ Recharger le dock")
        b_rel.clicked.connect(lambda: self.lancer_action("barre.recharger"))
        pos_h.addWidget(b_rel)
        pos_h.addStretch()
        l_barre.addLayout(pos_h)
        self.tbl_barre = self._table(["Réglage", "Valeur"])
        l_barre.addWidget(self.tbl_barre)
        self.onglets.addTab(w_barre, "🧭 Barre")

        # ICONES
        w_ico = QWidget(); l_ico = QVBoxLayout(w_ico)
        ico_h = QHBoxLayout()
        b_dev = QPushButton("🔓 Déverrouiller les lanceurs")
        b_dev.setProperty("class", "green")
        b_dev.clicked.connect(lambda: self.lancer_action("icones.deverrouiller"))
        ico_h.addWidget(b_dev)
        b_relico = QPushButton("♻ Recharger les icônes")
        b_relico.clicked.connect(lambda: self.lancer_action("icones.recharger"))
        ico_h.addWidget(b_relico)
        ico_h.addStretch()
        l_ico.addLayout(ico_h)
        self.lbl_lanceurs = QLabel("…")
        self.lbl_lanceurs.setStyleSheet("color:#94a3b8; font-family:'Fira Code',monospace;")
        l_ico.addWidget(self.lbl_lanceurs)
        self.tbl_icones = self._table(["Réglage", "Valeur"])
        l_ico.addWidget(self.tbl_icones)
        self.onglets.addTab(w_ico, "🗂 Icônes")

        # VERROUS
        w_ver = QWidget(); l_ver = QVBoxLayout(w_ver)
        ver_h = QHBoxLayout()
        b_lever = QPushButton("🔓 Tout lever")
        b_lever.setProperty("class", "amber")
        b_lever.clicked.connect(lambda: self.lancer_action("verrous.tout-lever"))
        ver_h.addWidget(b_lever)
        ver_h.addStretch()
        l_ver.addLayout(ver_h)
        self.lbl_dconf = QLabel("…")
        self.lbl_dconf.setStyleSheet("color:#94a3b8; font-family:'Fira Code',monospace;")
        self.lbl_dconf.setWordWrap(True)
        l_ver.addWidget(self.lbl_dconf)
        self.tbl_verrous = self._table(["Verrou", "État"])
        l_ver.addWidget(self.tbl_verrous)
        self.onglets.addTab(w_ver, "🔒 Verrous")

        # ECRANS
        w_ecr = QWidget(); l_ecr = QVBoxLayout(w_ecr)
        ecr_h = QHBoxLayout()
        b_mir = QPushButton("Miroir")
        b_mir.clicked.connect(lambda: self.confirmer("ecrans.miroir", "Basculer les écrans en MIROIR ?"))
        ecr_h.addWidget(b_mir)
        b_ete = QPushButton("Étendu")
        b_ete.clicked.connect(lambda: self.confirmer("ecrans.etendu", "Basculer les écrans en ÉTENDU ?"))
        ecr_h.addWidget(b_ete)
        ecr_h.addStretch()
        l_ecr.addLayout(ecr_h)
        self.tbl_ecrans = self._table(["Écran", "Détail"])
        l_ecr.addWidget(self.tbl_ecrans)
        note = QLabel(
            "HORS-LOGICIEL — l'overscan d'un téléviseur ne se corrige pas sous Wayland : Mutter n'expose "
            "ni underscan ni --transform, et baisser la définition n'y change rien (la TV zoome le signal). "
            "Réglage sur la télécommande : Menu → Image → Format d'image → Natif / Just Scan / Pixel par pixel / PC.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#fbbf24; font-size:11px; padding:6px; "
                           "background:#1c1917; border:1px solid #44403c; border-radius:6px;")
        l_ecr.addWidget(note)
        self.onglets.addTab(w_ecr, "🖵 Écrans")

        gl.addWidget(self.onglets)
        splitter.addWidget(gauche)

        # ── Droite : la trace ──
        droite = QWidget()
        dl = QVBoxLayout(droite)
        dl.setContentsMargins(0, 0, 0, 0)
        lbl_tr = QLabel("📋 TRACE — jarvis_logs.db · bureau_actions")
        lbl_tr.setFont(QFont("Ubuntu", 10, QFont.Weight.Bold))
        lbl_tr.setStyleSheet("color:#fb7185;")
        dl.addWidget(lbl_tr)
        self.tbl_trace = self._table(["Heure", "Domaine", "Avant", "Après", "Verdict"])
        dl.addWidget(self.tbl_trace)
        self.journal = QTextEdit()
        self.journal.setReadOnly(True)
        self.journal.setMaximumHeight(130)
        self.journal.setStyleSheet("background-color:#030712; color:#38bdf8; "
                                   "font-family:'Fira Code',monospace; font-size:11px;")
        dl.addWidget(self.journal)
        splitter.addWidget(droite)
        splitter.setSizes([620, 480])
        layout.addWidget(splitter)

        self.refresh_bureau()

    def _table(self, entetes):
        t = QTableWidget()
        t.setColumnCount(len(entetes))
        t.setHorizontalHeaderLabels(entetes)
        t.horizontalHeader().setSectionResizeMode(len(entetes) - 1, QHeaderView.ResizeMode.Stretch)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        t.verticalHeader().setVisible(False)
        return t

    @staticmethod
    def _fmt(v):
        if isinstance(v, bool):
            return "oui" if v else "non"
        return "—" if v is None else str(v)

    def _remplir(self, table, lignes):
        table.setRowCount(len(lignes))
        for r, cols in enumerate(lignes):
            for c, (texte, couleur) in enumerate(cols):
                it = QTableWidgetItem(texte)
                if couleur:
                    it.setForeground(QColor(couleur))
                table.setItem(r, c, it)

    def refresh_bureau(self):
        """Point d'entrée public UNIQUE — nom réservé pour la cascade F5 de gui_app."""
        e = get_bureau_etat()
        if not e.get("success"):
            self.journal.append(f"❌ {e.get('error')}")
            return

        conforme = e.get("conforme")
        self.lbl_conforme.setText("● CONFORME" if conforme else f"● {len(e['derives'])} DÉRIVE(S)")
        self.lbl_conforme.setStyleSheet(f"color: {'#4ade80' if conforme else '#fbbf24'};")

        self._remplir(self.tbl_barre, [[(c["libelle"], None), (self._fmt(c["valeur"]), "#e2e8f0")]
                                       for c in e["barre"]["cles"]])
        self._remplir(self.tbl_icones, [[(c["libelle"], None), (self._fmt(c["valeur"]), "#e2e8f0")]
                                        for c in e["icones"]["cles"]])
        self._remplir(self.tbl_verrous, [[(c["libelle"], None),
                                          (self._fmt(c["valeur"]), "#f87171" if c["valeur"] else "#4ade80")]
                                         for c in e["verrous"]["cles"]])

        l = e["icones"]["lanceurs"]
        self.lbl_lanceurs.setText(
            f"{l['total']} lanceurs · {l['executables']} exécutables · {l['trusted']} fiables "
            f"· {l['a_traiter']} à traiter    [{l['repertoire']}]")

        dc = e["verrous"]["dconf"]
        charge = ("les bases système sont chargées" if dc["profil_user"]
                  else "aucune base système chargée — ces verrous ne mordent pas")
        self.lbl_dconf.setText(f"dconf : {len(dc['locks'])} fichier(s) · "
                               f"{dc['inertes']} clé(s) inerte(s) — {charge}")

        ec = e["ecrans"]
        lignes = [[("Mode", None), (self._fmt(ec.get("mode")), "#818cf8")],
                  [("Pilotage", None), (self._fmt(ec.get("via")), "#94a3b8")]]
        for m in ec.get("moniteurs", []):
            lignes.append([(self._fmt(m.get("connecteur")), None),
                           (f"{m.get('nom') or m.get('modele')} · {m.get('mode_courant')}", "#e2e8f0")])
        self._remplir(self.tbl_ecrans, lignes)

        self._remplir(self.tbl_trace, [
            [(t["horodatage"][11:], "#64748b"), (t["domaine"], "#cbd5e1"),
             (self._fmt(t["valeur_avant"]), "#64748b"), (self._fmt(t["valeur_apres"]), "#e2e8f0"),
             (t["verdict"], COULEUR_VERDICT.get(t["verdict"], "#94a3b8"))]
            for t in e.get("traces", [])])

    def lancer_action(self, action, params=None):
        self.journal.append(f"▶ {action} …")
        self.worker = BureauWorker(action, params)          # référence gardée
        self.worker.finished_signal.connect(self.on_action_finished)
        self.worker.start()

    def on_action_finished(self, res):
        verdict = res.get("verdict", "?")
        msg = res.get("message") or res.get("error") or ""
        couleur = COULEUR_VERDICT.get(verdict, "#94a3b8")
        self.journal.append(f'<span style="color:{couleur}">■ {verdict}</span> — {msg}')
        self.refresh_bureau()

    def confirmer(self, action, question):
        rep = QMessageBox.question(
            self, "Confirmation", question + "\n\nUn retour arrière est tracé (colonne « reversible »).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if rep == QMessageBox.StandardButton.Yes:
            self.lancer_action(action)
