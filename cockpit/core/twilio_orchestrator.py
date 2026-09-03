#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TWILIO CONVERSATION ORCHESTRATOR ENGINE (v2)
Automatic multi-channel capture, routing, Memory Store linkage, Intelligence operators, and Active TwiML generation.
"""

import os
import json
import time
import urllib.request
import urllib.parse
import base64

CONVERSATIONS_V2_BASE = "https://conversations.twilio.com/v2"

class TwilioConversationOrchestrator:
    def __init__(self, account_sid: str = None, auth_token: str = None, phone_number: str = None):
        self.account_sid = account_sid or os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.auth_token = auth_token or os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.phone_number = phone_number or os.environ.get("TWILIO_PHONE_NUMBER", "")

    def get_auth_headers(self) -> dict:
        creds = (self.account_sid + ":" + self.auth_token).encode("utf-8")
        auth_header = "Basic " + base64.b64encode(creds).decode("utf-8")
        return {
            "Authorization": auth_header,
            "Content-Type": "application/json"
        }

    def is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token)

    def create_configuration(self, display_name: str, memory_store_id: str,
                             grouping_type: str = "GROUP_BY_PROFILE",
                             enable_memory_extraction: bool = True,
                             enable_sms: bool = True,
                             enable_whatsapp: bool = True,
                             enable_voice_active_only: bool = True,
                             intelligence_config_ids: list = None) -> dict:
        """
        Crée une configuration d'orchestration Twilio (Conversations v2).
        RÈGLE CRITIQUE DOUBLE FACTURATION :
          Si voice active (TwiML ConversationRelay / Transcription) -> PAS de captureRules dans VOICE.
        """
        payload = self._build_config_payload(
            display_name, memory_store_id, grouping_type, enable_memory_extraction,
            enable_sms, enable_whatsapp, enable_voice_active_only, intelligence_config_ids
        )

        if not self.is_configured():
            return {
                "success": False,
                "error": "TWILIO_ACCOUNT_SID et TWILIO_AUTH_TOKEN non configurés.",
                "mock_config": payload
            }

        try:
            req = urllib.request.Request(
                f"{CONVERSATIONS_V2_BASE}/ControlPlane/Configurations",
                data=json.dumps(payload).encode("utf-8"),
                headers=self.get_auth_headers(),
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e), "payload": payload}

    def _build_config_payload(self, display_name, memory_store_id, grouping_type,
                              enable_memory_extraction, enable_sms, enable_whatsapp,
                              enable_voice_active_only, intelligence_config_ids):
        phone = self.phone_number or "+15551234567"
        channel_settings = {}

        if enable_sms:
            channel_settings["SMS"] = {
                "captureRules": [
                    {"from": phone, "to": "*", "metadata": {}},
                    {"from": "*", "to": phone, "metadata": {}}
                ],
                "statusTimeouts": {"inactive": 10, "closed": 60}
            }

        if enable_whatsapp:
            channel_settings["WHATSAPP"] = {
                "captureRules": [
                    {"from": "whatsapp:" + phone, "to": "*", "metadata": {}},
                    {"from": "*", "to": "whatsapp:" + phone, "metadata": {}}
                ],
                "statusTimeouts": {"inactive": 10, "closed": 60}
            }

        if enable_voice_active_only:
            # Sécurité anti-double facturation STT : omit captureRules pour voix active TwiML
            channel_settings["VOICE"] = {
                "statusTimeouts": None
            }
        else:
            # Capture passive (appels agents humains sans TwiML active)
            channel_settings["VOICE"] = {
                "captureRules": [
                    {"from": "*", "to": phone, "metadata": {"callType": "PSTN"}},
                    {"from": "*", "to": phone, "metadata": {"callType": "CLIENT"}}
                ]
            }

        payload = {
            "displayName": display_name,
            "description": "Configuration unifiée JARVIS Conversation Orchestrator",
            "conversationGroupingType": grouping_type,
            "memoryStoreId": memory_store_id,
            "memoryExtractionEnabled": enable_memory_extraction,
            "channelSettings": channel_settings
        }

        if intelligence_config_ids:
            payload["intelligenceConfigurationIds"] = intelligence_config_ids

        return payload

    def generate_twiml_conversation_relay(self, websocket_url: str, config_id: str, tts_provider: str = "ElevenLabs", voice: str = "custom") -> str:
        """Génère le TwiML sécurisé pour ConversationRelay sans double facturation STT."""
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<Response>',
            '  <Connect>',
            f'    <ConversationRelay url="{websocket_url}" conversationConfiguration="{config_id}" ttsProvider="{tts_provider}" voice="{voice}" />',
            '  </Connect>',
            '</Response>'
        ]
        return "\n".join(lines)

    def generate_twiml_transcription_attachment(self, conversation_id: str, welcome_prompt: str = "Bienvenue sur JARVIS OS.") -> str:
        """Génère le TwiML pour attacher la transcription à une conversation existante."""
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<Response>',
            '  <Start>',
            f'    <Transcription conversationId="{conversation_id}"/>',
            '  </Start>',
            f'  <Say language="fr-FR">{welcome_prompt}</Say>',
            '</Response>'
        ]
        return "\n".join(lines)

    def list_conversations(self, status: str = "ACTIVE", page_size: int = 10) -> dict:
        """Liste les conversations actives ou fermées."""
        if not self.is_configured():
            return {"success": False, "error": "Twilio non configuré."}
        try:
            url = f"{CONVERSATIONS_V2_BASE}/Conversations?Status={status}&PageSize={page_size}"
            req = urllib.request.Request(url, headers=self.get_auth_headers())
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {"success": True, "conversations": data.get("conversations", [])}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def close_conversation(self, conversation_id: str) -> dict:
        """Ferme explicitement une conversation pour déclencher l'extraction mémoire et les opérateurs d'Intelligence."""
        if not self.is_configured():
            return {"success": False, "error": "Twilio non configuré."}
        try:
            url = f"{CONVERSATIONS_V2_BASE}/Conversations/{conversation_id}"
            payload = json.dumps({"status": "CLOSED"}).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers=self.get_auth_headers(), method="PATCH")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e)}
