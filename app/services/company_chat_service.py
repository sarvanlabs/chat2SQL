import json
import re
from typing import Any, Dict, List, Optional

from app.core.orchestrator import Orchestrator
from app.db.company_repository import get_company_profile, search_company


class CompanyChatService:
    """
    MVP "chat-to-company-profile" service.

    - Uses the LLM only to extract identifiers (CIN / company name) and write the final answer.
    - Uses deterministic DB functions for all data retrieval.
    """

    def __init__(self) -> None:
        self.llm = Orchestrator()

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Try to extract a single top-level JSON object from model output.
        """
        if not text:
            return None

        text = text.strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                return json.loads(text)
            except Exception:
                pass

        # Fallback: find the first {...} block
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None

    async def _extract_intent_and_filters(self, user_query: str) -> Dict[str, Any]:
        prompt = f"""
        You are a JSON extraction assistant for a company database.

        Extract the user's intent and relevant fields for querying the company database.
        ONLY return a JSON object with this schema:
        {{
        "action": "company_profile" | "company_list_by_filters" | "general_chat" | "unknown",
        "cin": string | null,
        "company_name": string | null,
        "roc_code": string | null,
        "location": string | null,
        "domain_keywords": string | null,
        "date_of_incorporation": string | null
        }}

        Rules:
        - CIN is the unique 21-character identifier (uppercase). If the question includes a CIN, set it.
        - If the question asks about a single company (e.g., "tell me about ...", "profile of ...", "status of ..."),
        infer company_name if CIN is not present.
        - If a ROC code is present, put it in roc_code (otherwise null).
        - If the question asks for multiple companies (e.g., "give me companies", "list companies", "show companies"),
        set action to "company_list_by_filters".
        - If it says "registered in <place>" or similar, set location to <place>.
        - If it says "registered on <date>" / "incorporated on <date>", set date_of_incorporation to YYYY-MM-DD.
        - If it says a business/domain like "data, AI domain", set domain_keywords to those words/phrase.
        - If the question is not about company data (e.g., greetings, "how are you", "what are you doing"),
        set action to "general_chat" and set all other fields to null.
        - If action is company_list_by_filters, cin/company_name may be null.
        - If you cannot identify, use action "unknown" and set fields conservatively to null.

        User question:
        {user_query}
        """
        model_text = await self.llm.generate_text(prompt)
        data = self._extract_json(model_text) or {}
        return {
            "action": data.get("action"),
            "cin": data.get("cin"),
            "company_name": data.get("company_name"),
            "roc_code": data.get("roc_code"),
            "location": data.get("location"),
            "domain_keywords": data.get("domain_keywords"),
            "date_of_incorporation": data.get("date_of_incorporation"),
        }

    async def _generate_final_answer(
        self,
        user_query: str,
        payload: Dict[str, Any],
        payload_type: str,
    ) -> str:
        # Provide compact context to the model.
        payload_json = json.dumps(payload, ensure_ascii=False)
        prompt = f"""
        You are a helpful assistant answering questions about an Indian companies dataset.

        Use ONLY the provided JSON data below to answer the user's question.
        If the data needed is not present, say so and ask for clarification.

        Data type: {payload_type}

        JSON:
        {payload_json}

        User question:
        {user_query}

        Answer guidelines:
        - Be humble and helpful.
        - Be concise and direct.
        - Do not invent values that aren't present in the JSON.
        - When relevant, include the CIN and company name.
        """
        return await self.llm.generate_text(prompt)

    async def _generate_general_chat_answer(self, user_query: str) -> str:
        prompt = f"""
            You are a helpful assistant.
            Answer the user normally to the best of your ability.

            User message:
            {user_query}
            """
        return await self.llm.generate_text(prompt)

    async def handle(self, user_query: str) -> str:
        user_query = (user_query or "").strip()
        if not user_query:
            return "Please enter a question."

        identifiers = await self._extract_intent_and_filters(user_query)
        action = identifiers.get("action")
        cin = identifiers.get("cin")
        company_name = identifiers.get("company_name")
        roc_code = identifiers.get("roc_code")
        location = identifiers.get("location")
        domain_keywords = identifiers.get("domain_keywords")
        date_of_incorporation = identifiers.get("date_of_incorporation")

        if action == "general_chat":
            return await self._generate_general_chat_answer(user_query)

        # Default to profile if the model is uncertain but gives CIN/name.
        if action == "unknown":
            action = "company_profile" if cin or company_name else "unknown"

        # If CIN is provided, treat it as primary key.
        if action == "company_profile" and isinstance(cin, str) and cin.strip():
            profile = get_company_profile(cin=cin)
            if not profile:
                return f"I couldn't find a company for CIN `{cin}`."
            return await self._generate_final_answer(
                user_query, profile, payload_type="company_profile"
            )

        # Otherwise, profile search by company name + optional ROC.
        if (
            action == "company_profile"
            and isinstance(company_name, str)
            and company_name.strip()
        ):
            candidates = search_company(
                cin=None,
                company_name=company_name,
                roc_code=roc_code,
                top_k=5,
            )
            if not candidates:
                return (
                    "I couldn't find any matching company. "
                    "Please share the exact company name or CIN."
                )
            if len(candidates) == 1:
                profile = get_company_profile(cin=candidates[0]["CIN"])
                if not profile:
                    return (
                        "I found the company, but couldn't fetch its profile right now."
                    )
                return await self._generate_final_answer(
                    user_query, profile, payload_type="company_profile"
                )

            # Multiple matches: ask a clarification question deterministically.
            top = candidates[:3]
            options = ", ".join([f"{c['company_name']} (CIN: {c['CIN']})" for c in top])
            return (
                "I found multiple matching companies. Which one do you mean?\n"
                f"Options: {options}\n"
                "Reply with the CIN (preferred) or the exact company name."
            )

        # Company list by filters.
        if action == "company_list_by_filters":
            from app.db.company_repository import search_companies_by_filters

            try:
                results = search_companies_by_filters(
                    location=location,
                    domain_keywords=domain_keywords,
                    date_of_incorporation=date_of_incorporation,
                    top_k=10,
                )
            except Exception as e:
                return (
                    "I couldn't process your date filter. "
                    "Please specify a valid year (e.g., '2025') or full date 'YYYY-MM-DD'."
                )

            if not results:
                return (
                    "I couldn't find any companies matching your filters. "
                    "Try changing the location or domain keywords (e.g., 'data analytics', 'IT services')."
                )

            payload = {
                "matches": results,
                "filters": {
                    "location": location,
                    "domain_keywords": domain_keywords,
                    "date_of_incorporation": date_of_incorporation,
                },
            }
            return await self._generate_final_answer(
                user_query, payload, payload_type="company_list"
            )

        # If we still don't recognize a company-data intent, answer normally (no DB calls).
        return await self._generate_general_chat_answer(user_query)
