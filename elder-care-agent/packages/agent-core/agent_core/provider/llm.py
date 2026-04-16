from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from dateutil.parser import isoparse
from typing import Any, Callable, TypeVar

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agent_core.config import get_settings
from agent_core.prompts.loader import load_prompt
from agent_core.schemas.common import (
    CognitionDecision,
    ElderResponsePlan,
    FamilyInstructionResult,
    IntentClassification,
    MoodSignal,
    PrescriptionExtraction,
    PrescriptionMedicationItem,
    ProfileCandidateSet,
    RelayMessageResult,
    RiskSignal,
)

T = TypeVar('T')
logger = logging.getLogger(__name__)

HIGH_RISK_KEYWORDS = {
    'critical': ['胸痛', '呼吸困难', '不能呼吸', '跌倒', '摔倒', '自杀', '不想活了'],
    'high': ['头晕厉害', '意识混乱', '完全忘了', '不肯吃药'],
    'medium': ['难过', '心情不好', '记不住', '忘记了'],
}


class LLMProvider:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._chat = None
        if self.settings.llm_api_key:
            try:
                self._chat = ChatOpenAI(
                    model=self.settings.llm_model,
                    api_key=self.settings.llm_api_key,
                    base_url=self.settings.llm_base_url,
                    temperature=0.2,
                )
            except Exception as exc:
                logger.warning('failed to initialize ChatOpenAI, falling back to local heuristics: %s', exc)
                self._chat = None

    async def analyze_mood(self, text: str, context: dict[str, Any]) -> MoodSignal:
        if not self._chat:
            return self._fallback_mood(text)
        prompt = load_prompt('elder_mood')
        return await self._safe_structured_call(
            call_name='analyze_mood',
            system_prompt=prompt,
            user_content=self._format_context(text, context),
            output_model=MoodSignal,
            fallback=lambda: self._fallback_mood(text),
        )

    async def analyze_risk(self, text: str, context: dict[str, Any]) -> RiskSignal:
        if not self._chat:
            return self._fallback_risk(text)
        prompt = load_prompt('elder_risk')
        return await self._safe_structured_call(
            call_name='analyze_risk',
            system_prompt=prompt,
            user_content=self._format_context(text, context),
            output_model=RiskSignal,
            fallback=lambda: self._fallback_risk(text),
        )

    async def classify_elder_intent(self, text: str, context: dict[str, Any]) -> IntentClassification:
        if not self._chat:
            return self._normalize_intent_result(text, self._fallback_intent(text))
        prompt = load_prompt('elder_intent')
        intent = await self._safe_structured_call(
            call_name='classify_elder_intent',
            system_prompt=prompt,
            user_content=self._format_context(text, context),
            output_model=IntentClassification,
            fallback=lambda: self._fallback_intent(text),
        )
        return self._normalize_intent_result(text, intent)

    async def extract_memory_candidates(self, text: str, context: dict[str, Any]) -> ProfileCandidateSet:
        if not self._chat:
            return self._fallback_memory(text)
        prompt = load_prompt('memory_extract')
        return await self._safe_structured_call(
            call_name='extract_memory_candidates',
            system_prompt=prompt,
            user_content=self._format_context(text, context),
            output_model=ProfileCandidateSet,
            fallback=lambda: self._fallback_memory(text),
        )

    async def analyze_family_instruction(self, text: str, context: dict[str, Any]) -> FamilyInstructionResult:
        if not self._chat:
            return self._fallback_family_instruction(text)
        prompt = load_prompt('family_instruction')
        return await self._safe_structured_call(
            call_name='analyze_family_instruction',
            system_prompt=prompt,
            user_content=self._format_context(text, context),
            output_model=FamilyInstructionResult,
            fallback=lambda: self._fallback_family_instruction(text),
        )

    async def parse_prescription(self, supporting_text: str, image_urls: list[str]) -> PrescriptionExtraction:
        if not self._chat:
            return self._fallback_prescription(supporting_text, has_images=bool(image_urls))
        prompt = load_prompt('prescription_parse')
        try:
            extraction = await self._tolerant_json_call(
                prompt,
                supporting_text or '请基于上传图像提取药方信息。',
                PrescriptionExtraction,
                image_urls=image_urls,
            )
            logger.info(
                'prescription parse completed: medications=%s needs_confirmation=%s uncertainty_notes=%s raw_observations=%s',
                len(extraction.medications),
                extraction.needs_confirmation,
                extraction.uncertainty_notes,
                extraction.raw_observations[:3],
            )
            return extraction
        except Exception as exc:
            logger.warning('prescription multimodal parse failed, falling back to safe review mode: %s', exc)
            return self._fallback_prescription(supporting_text, has_images=bool(image_urls))

    async def summarize_relay(self, text: str, direction: str) -> RelayMessageResult:
        if not self._chat:
            return self._fallback_relay(text, direction)
        prompt = load_prompt('relay_message')
        content = f'方向: {direction}\n原始文本: {text}'
        return await self._safe_structured_call(
            call_name='summarize_relay',
            system_prompt=prompt,
            user_content=content,
            output_model=RelayMessageResult,
            fallback=lambda: self._fallback_relay(text, direction),
        )

    async def decide_cognition(self, context: dict[str, Any]) -> CognitionDecision:
        if not self._chat:
            return self._fallback_cognition(context)
        prompt = load_prompt('cognition_decision')
        return await self._safe_structured_call(
            call_name='decide_cognition',
            system_prompt=prompt,
            user_content=json.dumps(context, ensure_ascii=False, indent=2),
            output_model=CognitionDecision,
            fallback=lambda: self._fallback_cognition(context),
        )

    async def generate_elder_response(self, text: str, context: dict[str, Any]) -> ElderResponsePlan:
        if self._should_force_medication_confirmation_response(text, context):
            return self._medication_confirmation_response(context)
        if self._should_use_freeform_chat(text, context):
            return await self._freeform_chat_response(text, context)
        if not self._chat:
            return self._fallback_response(text, context)
        prompt = load_prompt('elder_response')
        response = await self._safe_structured_call(
            call_name='generate_elder_response',
            system_prompt=prompt,
            user_content=self._format_context(text, context),
            output_model=ElderResponsePlan,
            fallback=lambda: self._fallback_response(text, context),
        )
        return self._normalize_response_plan(text, context, response)

    async def _safe_structured_call(
        self,
        call_name: str,
        system_prompt: str,
        user_content: str,
        output_model: type[T],
        fallback: Callable[[], T],
        image_urls: list[str] | None = None,
    ) -> T:
        try:
            return await self._structured_call(system_prompt, user_content, output_model, image_urls=image_urls)
        except Exception as exc:
            logger.warning('%s structured parse failed, falling back to heuristics: %s', call_name, exc)
            return fallback()

    async def _text_call(self, system_prompt: str, user_content: str, image_urls: list[str] | None = None) -> str:
        assert self._chat is not None
        human = self._build_human_message(user_content, image_urls)
        message = await self._chat.ainvoke([SystemMessage(content=system_prompt), human])
        text = self._message_text(message).strip()
        if not text:
            raise ValueError('empty text response from model')
        return text

    async def _structured_call(self, system_prompt: str, user_content: str, output_model: type[T], image_urls: list[str] | None = None) -> T:
        assert self._chat is not None
        model = self._chat.with_structured_output(output_model)
        if image_urls:
            content: list[dict[str, Any]] = []
            for image_url in image_urls:
                content.append({'type': 'image_url', 'image_url': {'url': image_url}})
            content.append({'type': 'text', 'text': user_content})
            human = HumanMessage(content=content)
        else:
            human = HumanMessage(content=user_content)
        return await model.ainvoke([SystemMessage(content=system_prompt), human])

    async def _tolerant_json_call(self, system_prompt: str, user_content: str, output_model: type[T], image_urls: list[str] | None = None) -> T:
        assert self._chat is not None
        human = self._build_human_message(user_content, image_urls)
        message = await self._chat.ainvoke([SystemMessage(content=system_prompt), human])
        raw_text = self._message_text(message)
        return self._parse_json_payload(raw_text, output_model)

    async def _freeform_chat_response(self, text: str, context: dict[str, Any]) -> ElderResponsePlan:
        reply = await self.chat_with_elder(text, context)
        return self._plain_response_plan(reply, context)

    async def chat_with_elder(self, text: str, context: dict[str, Any]) -> str:
        if not self._chat:
            return self._fallback_chat_reply(text, context)
        prompt = load_prompt('elder_chat')
        try:
            reply = await self._text_call(prompt, self._format_chat_context(text, context))
        except Exception as exc:
            logger.warning('chat_with_elder text call failed, falling back to heuristics: %s', exc)
            return self._fallback_chat_reply(text, context)
        return self._normalize_text_reply(reply, text, context)

    def _build_human_message(self, user_content: str, image_urls: list[str] | None = None) -> HumanMessage:
        if image_urls:
            content: list[dict[str, Any]] = []
            for image_url in image_urls:
                content.append({'type': 'image_url', 'image_url': {'url': image_url}})
            content.append({'type': 'text', 'text': user_content})
            return HumanMessage(content=content)
        return HumanMessage(content=user_content)

    def _message_text(self, message: AIMessage) -> str:
        content = message.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and item.get('type') == 'text':
                    text = item.get('text')
                    if isinstance(text, str):
                        parts.append(text)
            return '\n'.join(part for part in parts if part).strip()
        return str(content)

    def _parse_json_payload(self, raw_text: str, output_model: type[T]) -> T:
        text = raw_text.strip()
        if text.startswith('```'):
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text).strip()
        start = text.find('{')
        if start == -1:
            raise ValueError(f'no json object found in model response: {text[:200]}')
        payload, _ = json.JSONDecoder().raw_decode(text[start:])
        if output_model is PrescriptionExtraction:
            payload = self._normalize_prescription_payload(payload)
        return output_model.model_validate(payload)

    def _normalize_prescription_payload(self, payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload

        medications = (
            payload.get('medications')
            or payload.get('药物列表')
            or payload.get('药物')
            or payload.get('medicines')
            or []
        )
        normalized_medications: list[dict[str, Any]] = []
        if isinstance(medications, list):
            for item in medications:
                if not isinstance(item, dict):
                    continue
                normalized = dict(item)
                normalized['medication_name'] = (
                    normalized.get('medication_name')
                    or normalized.get('name')
                    or normalized.get('药名')
                    or normalized.get('药物名称')
                    or ''
                )
                normalized['dose'] = (
                    normalized.get('dose')
                    or normalized.get('剂量')
                    or normalized.get('用量')
                    or normalized.get('规格')
                    or ''
                )
                normalized['frequency'] = (
                    normalized.get('frequency')
                    or normalized.get('频次')
                    or normalized.get('用法频次')
                    or normalized.get('服用频次')
                    or ''
                )
                normalized['meal_timing'] = (
                    normalized.get('meal_timing')
                    or normalized.get('餐前餐后')
                    or normalized.get('服用时机')
                    or normalized.get('用药时机')
                    or ''
                )
                normalized['suggested_times'] = self._ensure_list(
                    normalized.get('suggested_times')
                    or normalized.get('每日时间建议')
                    or normalized.get('建议时间')
                    or normalized.get('服药时间')
                )
                normalized['start_date'] = normalized.get('start_date') or normalized.get('开始日期')
                normalized['end_date'] = normalized.get('end_date') or normalized.get('结束日期')
                normalized['confidence'] = self._coerce_confidence(
                    normalized.get('confidence') or normalized.get('置信度')
                )
                normalized['uncertain_fields'] = self._ensure_list(
                    normalized.get('uncertain_fields') or normalized.get('不确定字段')
                )
                normalized_medications.append(normalized)

        payload['medications'] = normalized_medications
        payload['overall_summary'] = (
            payload.get('overall_summary')
            or payload.get('overallSummary')
            or payload.get('总结')
            or payload.get('整体总结')
            or ''
        )
        payload['uncertainty_notes'] = self._ensure_list(
            payload.get('uncertainty_notes')
            or payload.get('uncertaintyNotes')
            or payload.get('不确定说明')
            or payload.get('注意事项')
        )
        payload['needs_confirmation'] = bool(
            payload.get('needs_confirmation')
            or payload.get('needsConfirmation')
            or payload.get('需要确认')
            or any(item.get('uncertain_fields') for item in normalized_medications)
        )
        payload['raw_observations'] = self._ensure_list(
            payload.get('raw_observations')
            or payload.get('rawObservations')
            or payload.get('原始观察')
            or payload.get('图像观察')
        )
        if not payload['overall_summary'] and normalized_medications:
            payload['overall_summary'] = '；'.join(
                ' '.join(part for part in [item.get('medication_name', ''), item.get('dose', ''), item.get('frequency', '')] if part).strip()
                for item in normalized_medications
            )
        return payload

    def _ensure_list(self, value: Any) -> list[Any]:
        if value is None or value == '':
            return []
        if isinstance(value, list):
            return value
        return [value]

    def _coerce_confidence(self, value: Any) -> float:
        if value is None or value == '':
            return 0.8
        if isinstance(value, (int, float)):
            return max(0.0, min(1.0, float(value)))
        if isinstance(value, str):
            stripped = value.strip().rstrip('%')
            try:
                parsed = float(stripped)
            except ValueError:
                return 0.8
            if '%' in value or parsed > 1:
                parsed = parsed / 100
            return max(0.0, min(1.0, parsed))
        return 0.8

    def _format_context(self, text: str, context: dict[str, Any]) -> str:
        return json.dumps({'user_text': text, 'context': context}, ensure_ascii=False, indent=2)

    def _format_chat_context(self, text: str, context: dict[str, Any]) -> str:
        trimmed_context = {
            'recent_conversations': context.get('recent_conversations', [])[-6:],
            'profile': context.get('profile', {}),
            'daily_status': context.get('daily_status', {}),
            'mood_signal': context.get('mood_signal', {}),
            'risk_signal': context.get('risk_signal', {}),
            'intent': context.get('intent', {}),
        }
        return json.dumps({'user_text': text, 'context': trimmed_context}, ensure_ascii=False, indent=2)

    def _fallback_mood(self, text: str) -> MoodSignal:
        label = 'calm'
        summary = '情绪整体平稳。'
        confidence = 0.72
        if any(word in text for word in ['不开心', '不高兴', '难过', '烦', '不舒服', '担心', '心情不好']):
            label, summary, confidence = 'low', '存在低落或担忧信号。', 0.8
        elif any(word in text for word in ['着急', '急', '慌', '害怕']):
            label, summary, confidence = 'anxious', '存在紧张或焦虑信号。', 0.83
        elif any(word in text for word in ['开心', '高兴', '放心']):
            label, summary, confidence = 'positive', '表达积极或安心。', 0.82
        return MoodSignal(label=label, confidence=confidence, summary=summary)

    def _fallback_risk(self, text: str) -> RiskSignal:
        lowered = text.strip()
        for level, keywords in HIGH_RISK_KEYWORDS.items():
            matches = [kw for kw in keywords if kw in lowered]
            if matches:
                return RiskSignal(
                    level=level,
                    indicators=matches,
                    rationale='命中高风险关键词。',
                    requires_alert=level in {'high', 'critical'},
                )
        return RiskSignal(
            level='low' if any(word in lowered for word in ['忘了', '记不清']) else 'none',
            indicators=['健忘'] if '忘' in lowered else [],
            rationale='未发现急性高风险表达。',
            requires_alert=False,
        )

    def _fallback_intent(self, text: str) -> IntentClassification:
        if '帮我跟' in text or '跟我儿子说' in text or '跟我女儿说' in text:
            return IntentClassification(primary_intent='family_relay', needs_tool_call=True, family_message=text, confidence=0.92, rationale='存在明显带话模式。')
        if self._is_medication_confirmation_text(text):
            return IntentClassification(primary_intent='medication_confirmation', needs_tool_call=True, medication_taken=True, confidence=0.9, rationale='存在吃药确认表达。')
        if any(word in text for word in ['通知', '刚才谁说', '家里有话吗']):
            return IntentClassification(primary_intent='ask_notice', needs_tool_call=False, confidence=0.75, rationale='用户在询问通知。')
        if any(word in text for word in ['难受', '不舒服', '胸痛', '呼吸困难']):
            return IntentClassification(primary_intent='distress_signal', needs_tool_call=True, confidence=0.88, rationale='存在身体不适表达。')
        return IntentClassification(primary_intent='chat', needs_tool_call=False, confidence=0.68, rationale='默认普通聊天。')

    def _fallback_memory(self, text: str) -> ProfileCandidateSet:
        stable_updates: dict[str, Any] = {}
        daily_updates: dict[str, Any] = {}
        risk_updates: dict[str, Any] = {}
        review_items: list[dict[str, Any]] = []
        people = [person for person in ['儿子', '女儿', '老伴', '孙子', '孙女'] if person in text]
        if people:
            stable_updates['frequently_mentioned_people'] = people
        if '早上' in text and '起' in text:
            stable_updates['usual_wake_time'] = '07:00'
        if '喜欢' in text:
            stable_updates['liked_topics'] = [text.split('喜欢', 1)[1][:12].strip('，。 ')]
        chronic_conditions = [item for item in ['高血压', '糖尿病', '冠心病', '心脏病', '失眠', '焦虑', '抑郁', '帕金森', '阿尔茨海默病'] if item in text]
        if chronic_conditions:
            stable_updates['chronic_conditions'] = chronic_conditions
        stable_time_patterns = [
            ('usual_wake_time', ['起床', '醒来', '醒了']),
            ('usual_breakfast_time', ['早餐', '早饭']),
            ('usual_lunch_time', ['午饭', '午餐', '中饭']),
            ('usual_dinner_time', ['晚饭', '晚餐']),
            ('usual_sleep_time', ['睡觉', '休息']),
        ]
        for key, hints in stable_time_patterns:
            value = self._extract_clock_by_context(text, hints, ['平时', '一般', '通常', '往常', '每天'])
            if value:
                stable_updates[key] = value

        daily_time_patterns = [
            ('woke_up_at', ['起床', '醒了', '醒来']),
            ('breakfast_at', ['早餐', '早饭']),
            ('lunch_at', ['午饭', '午餐', '中饭']),
            ('dinner_at', ['晚饭', '晚餐']),
            ('sleep_at', ['睡觉', '休息']),
        ]
        for key, hints in daily_time_patterns:
            value = self._extract_clock_by_context(text, hints, ['今天', '今早', '今天早上', '今天中午', '今天晚上', '今晚'])
            if value:
                daily_updates[key] = value
        if self._is_medication_confirmation_text(text):
            daily_updates['medication_taken'] = True
        if any(word in text for word in ['难过', '没精神', '不高兴']):
            daily_updates['mood'] = 'low'
            risk_updates['low_mood_trend'] = 'observed'
        if any(word in text for word in ['胸痛', '呼吸困难', '不想活了']):
            review_items.append({'reason': 'high_risk_expression', 'text': text})
        return ProfileCandidateSet(
            stable_updates=stable_updates,
            daily_updates=daily_updates,
            risk_updates=risk_updates,
            review_items=review_items,
            summary='基于当前对话提取到画像候选更新。',
        )

    def _extract_clock_by_context(self, text: str, hints: list[str], prefixes: list[str]) -> str | None:
        time_pattern = r'((?:\d{1,2}(?:[:：]\d{1,2}|点半|点\d{0,2}分?))|(?:[零〇一二两三四五六七八九十百]{1,4}点(?:半|[零〇一二两三四五六七八九十百]{1,4}分?)?))'
        hint_pattern = '|'.join(re.escape(hint) for hint in hints)
        prefix_pattern = '|'.join(re.escape(prefix) for prefix in prefixes)
        patterns = [
            rf'(?:{prefix_pattern})[^。；，,\n]*?{time_pattern}[^。；，,\n]*?(?:{hint_pattern})',
            rf'(?:{prefix_pattern})[^。；，,\n]*?(?:{hint_pattern})[^。；，,\n]*?{time_pattern}',
            rf'(?:{hint_pattern})[^。；，,\n]*?(?:{prefix_pattern})[^。；，,\n]*?{time_pattern}',
            rf'{time_pattern}[^。；，,\n]*?(?:{prefix_pattern})[^。；，,\n]*?(?:{hint_pattern})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return self._normalize_clock_text(match.group(1))
        return None

    def _normalize_clock_text(self, value: str) -> str:
        text = value.strip()
        colon_match = re.search(r'(\d{1,2})[:：](\d{1,2})', text)
        if colon_match:
            return f"{int(colon_match.group(1)):02d}:{int(colon_match.group(2)):02d}"
        chinese_match = re.search(r'(\d{1,2})点(?:(半)|(\d{1,2})分?)?', text)
        if chinese_match:
            hour = int(chinese_match.group(1))
            minute = 30 if chinese_match.group(2) else int(chinese_match.group(3) or 0)
            return f'{hour:02d}:{minute:02d}'
        chinese_number_match = re.search(r'([零〇一二两三四五六七八九十百]{1,4})点(?:(半)|([零〇一二两三四五六七八九十百]{1,4})分?)?', text)
        if chinese_number_match:
            hour = self._parse_chinese_number(chinese_number_match.group(1))
            minute = 30 if chinese_number_match.group(2) else self._parse_chinese_number(chinese_number_match.group(3) or '零')
            if hour is not None and minute is not None:
                return f'{hour:02d}:{minute:02d}'
        return text

    def _parse_chinese_number(self, value: str) -> int | None:
        text = value.strip()
        if not text:
            return None
        digits = {'零': 0, '〇': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
        if text in digits:
            return digits[text]
        if text == '十':
            return 10
        if '十' in text:
            left, _, right = text.partition('十')
            tens = 1 if left == '' else digits.get(left)
            ones = 0 if right == '' else digits.get(right)
            if tens is None or ones is None:
                return None
            return tens * 10 + ones
        total = 0
        for char in text:
            digit = digits.get(char)
            if digit is None:
                return None
            total = total * 10 + digit
        return total

    def _fallback_family_instruction(self, text: str) -> FamilyInstructionResult:
        if any(word in text for word in ['？', '?', '怎么样', '今天情况']):
            return FamilyInstructionResult(
                kind='query',
                summarized_notice='家属发起状态查询。',
                urgency='low',
                delivery_strategy=None,
                suitable_window=None,
                rationale='输入更像查询而不是需要转达的通知。',
                should_store_notice=False,
                query_answer='请查看仪表盘中的今日摘要。',
            )
        kind = 'message' if any(word in text for word in ['帮我告诉', '跟妈妈说', '留言']) else 'notice'
        urgency = 'critical' if any(word in text for word in ['立刻', '马上', '急诊']) else 'high' if any(word in text for word in ['赶紧', '尽快']) else 'medium'
        strategy = 'before_meal' if '吃饭' in text else 'evening' if '今晚' in text else 'now' if urgency in {'high', 'critical'} else 'next_free_slot'
        return FamilyInstructionResult(
            kind=kind,
            summarized_notice=text.strip().replace('\n', ' ')[:120],
            urgency=urgency,
            delivery_strategy=strategy,
            suitable_window='18:00-19:00' if strategy == 'before_meal' else '尽快在老人空闲时',
            rationale='基于关键词和语义规则估算紧急度与传达时机。',
            should_store_notice=kind == 'notice',
            relay_message=text if kind == 'message' else None,
        )

    def _fallback_prescription(self, supporting_text: str, has_images: bool = False) -> PrescriptionExtraction:
        lines = [line.strip() for line in supporting_text.splitlines() if line.strip()]
        if not lines:
            note = '已收到处方图片，但当前未得到可靠的结构化识别结果，请家属确认后再执行。' if has_images else '当前未得到可靠的处方文本，请家属确认后再执行。'
            return PrescriptionExtraction(
                medications=[],
                overall_summary='未能可靠识别药方内容，已标记为待家属确认。',
                uncertainty_notes=[note],
                needs_confirmation=True,
                raw_observations=[],
            )

        medications: list[PrescriptionMedicationItem] = []
        pattern = re.compile(
            r'(?P<name>[A-Za-z\u4e00-\u9fa5]{2,20})[：:\s]*(?P<dose>\d+(?:\.\d+)?(?:mg|g|ml|片|粒|袋|包))?\s*(?P<freq>每日\d次|一天\d次|早晚各\d次|早中晚各\d次|bid|tid|qd|睡前)?\s*(?P<meal>饭前|饭后|餐前|餐后)?'
        )
        for line in lines:
            match = pattern.search(line)
            if not match:
                continue
            name = match.group('name')
            if len(name) < 2:
                continue
            dose = match.group('dose') or ''
            freq = match.group('freq') or ''
            meal = match.group('meal') or ''
            uncertain = [field for field, value in [('dose', dose), ('frequency', freq), ('meal_timing', meal)] if not value]
            if '早晚' in freq or freq == 'bid':
                suggested = ['08:00', '20:00']
            elif '早中晚' in freq or freq == 'tid':
                suggested = ['08:00', '13:00', '20:00']
            else:
                suggested = ['08:00']
            medications.append(
                PrescriptionMedicationItem(
                    medication_name=name,
                    dose=dose,
                    frequency=freq,
                    meal_timing=meal,
                    suggested_times=suggested,
                    confidence=0.55 if uncertain else 0.82,
                    uncertain_fields=uncertain,
                )
            )

        if not medications:
            return PrescriptionExtraction(
                medications=[],
                overall_summary='未能从当前内容中可靠抽取药物条目，已标记为待家属确认。',
                uncertainty_notes=['当前结果不足以生成服药计划，请家属手动确认。'],
                needs_confirmation=True,
                raw_observations=lines[:10],
            )

        uncertainty_notes = []
        needs_confirmation = any(item.uncertain_fields for item in medications)
        if needs_confirmation:
            uncertainty_notes.append('至少一个药物字段不完整，需要家属确认后再执行。')
        summary = '；'.join(f"{item.medication_name} {item.dose} {item.frequency}".strip() for item in medications) or '未能可靠识别药方内容。'
        return PrescriptionExtraction(
            medications=medications,
            overall_summary=summary,
            uncertainty_notes=uncertainty_notes,
            needs_confirmation=needs_confirmation,
            raw_observations=lines[:10],
        )

    def _fallback_relay(self, text: str, direction: str) -> RelayMessageResult:
        cleaned = re.sub(r'^(帮我|麻烦你)?(跟|给)?', '', text).strip(' ，。')
        audience = 'family' if direction == 'elder_to_family' else 'elder'
        urgency = 'medium' if any(word in text for word in ['尽快', '今天', '马上']) else 'low'
        return RelayMessageResult(direction=direction, summary_text=cleaned[:120], audience=audience, urgency=urgency, rationale='已整理为简洁可转达消息。')

    def _fallback_cognition(self, context: dict[str, Any]) -> CognitionDecision:
        daily_status = context.get('daily_status', {})
        mood = (daily_status or {}).get('mood', '')
        if mood in {'anxious', 'distressed'}:
            return CognitionDecision(should_engage=False, rationale='当前情绪偏紧张，先不做认知互动。')
        now_ts = context.get('now_ts')
        if now_ts:
            try:
                now_hour = isoparse(str(now_ts)).hour
            except ValueError:
                now_hour = datetime.now().hour
        else:
            now_hour = datetime.now().hour
        if now_hour < 9 or now_hour > 20:
            return CognitionDecision(should_engage=False, rationale='当前时段不适合主动打扰。')
        return CognitionDecision(
            should_engage=True,
            theme='工作回忆',
            prompt='李阿姨，想听您说说以前的工作。您那时候最拿手、最有成就感的一件事是什么？',
            observation_focus='工作相关回忆的流畅度与细节表达',
            rationale='当前时段平稳，适合自然、温和地做工作回忆互动。',
            anomaly_signal='轻度观察',
        )

    def _normalize_intent_result(self, text: str, intent: IntentClassification) -> IntentClassification:
        if not self._should_treat_as_medication_confirmation(text, intent):
            return intent
        intent.primary_intent = 'medication_confirmation'
        intent.needs_tool_call = True
        intent.medication_taken = True
        intent.confidence = max(intent.confidence, 0.9)
        normalization_note = '命中吃药完成表达，按服药确认处理。'
        intent.rationale = normalization_note if not intent.rationale else f'{intent.rationale} {normalization_note}'
        return intent

    def _normalize_response_plan(self, text: str, context: dict[str, Any], response: ElderResponsePlan) -> ElderResponsePlan:
        if self._should_force_medication_confirmation_response(text, context):
            return self._medication_confirmation_response(context)
        if self._should_force_companion_reply(text, context, response):
            return self._companion_reply_plan(text, context)
        return response

    def _should_use_freeform_chat(self, text: str, context: dict[str, Any]) -> bool:
        if not self._chat:
            return False
        if self._looks_like_family_relay(text) or self._is_medication_confirmation_text(text):
            return False
        if context.get('selected_notices') or context.get('selected_family_messages') or context.get('selected_due_medications'):
            return False
        risk: dict[str, Any] = context.get('risk_signal', {})
        if risk.get('requires_alert'):
            return False
        primary_intent = self._intent_field(context.get('intent'), 'primary_intent')
        return primary_intent in {'chat', 'cognition_response', 'other'}

    def _should_treat_as_medication_confirmation(self, text: str, intent: IntentClassification) -> bool:
        if self._looks_like_family_relay(text):
            return False
        if intent.primary_intent == 'family_relay' and intent.family_message:
            return False
        return self._is_medication_confirmation_text(text)

    def _should_force_medication_confirmation_response(self, text: str, context: dict[str, Any]) -> bool:
        if self._looks_like_family_relay(text):
            return False
        intent = context.get('intent') or {}
        primary_intent = self._intent_field(intent, 'primary_intent')
        medication_taken = self._intent_field(intent, 'medication_taken')
        return bool(
            primary_intent == 'medication_confirmation'
            or medication_taken
            or self._is_medication_confirmation_text(text)
        )

    def _medication_confirmation_response(self, context: dict[str, Any]) -> ElderResponsePlan:
        risk: dict[str, Any] = context.get('risk_signal', {})
        cognition_decision = context.get('cognition_decision', {})
        lines: list[str] = []
        if risk.get('requires_alert'):
            lines.append('如果现在胸口难受、呼吸不顺或者摔倒了，请先立刻叫身边的人帮忙，必要时马上联系急救。')
        lines.append('我记下了，您刚才说药已经吃好了。')
        reply = ' '.join(lines[:2])
        cognition_prompt = cognition_decision.get('prompt') if isinstance(cognition_decision, dict) else None
        return ElderResponsePlan(
            reply_text=reply,
            subtitle=reply,
            deliver_notice_ids=[],
            deliver_message_ids=[],
            reminder_plan_ids=[],
            family_message_sent=False,
            cognition_prompt=cognition_prompt,
        )

    def _plain_response_plan(self, reply: str, context: dict[str, Any]) -> ElderResponsePlan:
        cognition_decision = context.get('cognition_decision', {})
        cognition_prompt = cognition_decision.get('prompt') if isinstance(cognition_decision, dict) else None
        return ElderResponsePlan(
            reply_text=reply,
            subtitle=reply,
            deliver_notice_ids=[],
            deliver_message_ids=[],
            reminder_plan_ids=[],
            family_message_sent=False,
            cognition_prompt=cognition_prompt,
        )

    def _should_force_companion_reply(self, text: str, context: dict[str, Any], response: ElderResponsePlan) -> bool:
        if not self._is_companion_request(text):
            return False
        if context.get('selected_notices') or context.get('selected_family_messages') or context.get('selected_due_medications'):
            return False
        return self._reply_is_generic(response.reply_text)

    def _companion_reply_plan(self, text: str, context: dict[str, Any]) -> ElderResponsePlan:
        reply = self._fallback_chat_reply(text, context)
        cognition_decision = context.get('cognition_decision', {})
        cognition_prompt = cognition_decision.get('prompt') if isinstance(cognition_decision, dict) else None
        return ElderResponsePlan(
            reply_text=reply,
            subtitle=reply,
            deliver_notice_ids=[],
            deliver_message_ids=[],
            reminder_plan_ids=[],
            family_message_sent=False,
            cognition_prompt=cognition_prompt,
        )

    def _intent_field(self, intent: Any, field: str) -> Any:
        if isinstance(intent, IntentClassification):
            return getattr(intent, field, None)
        if isinstance(intent, dict):
            return intent.get(field)
        return None

    def _fallback_response(self, text: str, context: dict[str, Any]) -> ElderResponsePlan:
        notices = context.get('selected_notices', [])
        due_medications = context.get('selected_due_medications', [])
        pending_messages = context.get('selected_family_messages', [])
        risk: dict[str, Any] = context.get('risk_signal', {})
        intent: dict[str, Any] = context.get('intent', {})
        lines: list[str] = []
        deliver_notice_ids: list[str] = []
        deliver_message_ids: list[str] = []
        reminder_plan_ids: list[str] = []
        if risk.get('requires_alert'):
            lines.append('如果现在胸口难受、呼吸不顺或者摔倒了，请先立刻叫身边的人帮忙，必要时马上联系急救。')
        if intent.get('primary_intent') == 'medication_confirmation' or intent.get('medication_taken'):
            lines.append('我记下了，您刚才说药已经吃好了。')
        if notices and intent.get('primary_intent') != 'medication_confirmation':
            deliver_notice_ids = [item['id'] for item in notices]
            lines.append('有一条家里人的话想和您说：' + notices[0]['summarized_notice'])
        if pending_messages and intent.get('primary_intent') != 'medication_confirmation':
            deliver_message_ids = [item['id'] for item in pending_messages]
            lines.append('还有家里留言：' + pending_messages[0]['summary_text'])
        if due_medications and intent.get('primary_intent') != 'medication_confirmation':
            reminder_plan_ids = [item['id'] for item in due_medications]
            lines.append('现在差不多该记得吃 ' + due_medications[0]['medication_name'] + ' 了。')
        if intent.get('primary_intent') == 'family_relay':
            lines.append('我已经帮您记下这条话，会转给家里人。')
        if not lines:
            lines.append(self._fallback_chat_reply(text, context))
        reply = ' '.join(lines[:2])
        return ElderResponsePlan(
            reply_text=reply,
            subtitle=reply,
            deliver_notice_ids=deliver_notice_ids,
            deliver_message_ids=deliver_message_ids,
            reminder_plan_ids=reminder_plan_ids,
            family_message_sent=intent.get('primary_intent') == 'family_relay',
            cognition_prompt=context.get('cognition_decision', {}).get('prompt'),
        )

    def _looks_like_family_relay(self, text: str) -> bool:
        normalized = text.strip()
        relay_markers = [
            '帮我跟',
            '帮我告诉',
            '替我跟',
            '转告',
            '跟我儿子说',
            '跟我女儿说',
            '给我儿子说',
            '给我女儿说',
            '跟家里人说',
        ]
        return any(marker in normalized for marker in relay_markers)

    def _is_companion_request(self, text: str) -> bool:
        normalized = text.strip()
        return any(
            token in normalized
            for token in [
                '讲个故事',
                '讲故事',
                '说个故事',
                '听故事',
                '说个笑话',
                '讲个笑话',
                '逗我开心',
                '陪我聊聊',
                '陪我说说话',
                '聊聊天',
                '给我讲讲',
            ]
        )

    def _reply_is_generic(self, text: str) -> bool:
        normalized = (text or '').strip()
        generic_replies = {
            '',
            '我在这儿，您慢慢说，我陪着您。',
            '我在这儿，您慢慢说。',
        }
        return normalized in generic_replies

    def _normalize_text_reply(self, reply: str, text: str, context: dict[str, Any]) -> str:
        cleaned = reply.strip()
        if not cleaned:
            return self._fallback_chat_reply(text, context)
        if len(cleaned) > 220:
            cleaned = cleaned[:220].rstrip('，。；,; ') + '。'
        return cleaned

    def _fallback_chat_reply(self, text: str, context: dict[str, Any]) -> str:
        normalized = text.strip()
        if self._is_story_request(normalized):
            return self._story_reply(context)
        if self._is_joke_request(normalized):
            return '那我说个轻松的：爷爷去量血压，医生说您今天很平稳。爷爷笑着说，那当然，我出门前先把老伴交代的话都记住了。'
        if any(token in normalized for token in ['你好', '你在吗', '在吗']):
            return '我在呢。您想聊聊今天的事，还是想听个小故事？'
        if any(token in normalized for token in ['无聊', '陪我聊聊', '陪我说说话', '聊聊天']):
            return '当然可以。您今天最想说哪件事，我慢慢听着。'
        return '我在这儿，您慢慢说，我陪着您。'

    def _is_story_request(self, text: str) -> bool:
        return any(token in text for token in ['讲个故事', '讲故事', '说个故事', '听故事'])

    def _is_joke_request(self, text: str) -> bool:
        return any(token in text for token in ['笑话', '逗我开心', '乐一乐'])

    def _story_reply(self, context: dict[str, Any]) -> str:
        topic = self._preferred_topic(context)
        if '花' in topic:
            return '那我给您讲个小故事：有位奶奶在阳台养了三盆花，她每天早上都轻轻说一声早安。花开得慢，她也不着急。到了春天第一天，最小那盆先开了，她高兴得一整天都在笑。'
        if '家' in topic or '家人' in topic:
            return '那我给您讲个小故事：有位奶奶每天傍晚都把饭桌擦得干干净净，她总说家里人回来时，屋里要有热乎气。后来有一天，孩子们提早回来了，一进门闻到饭香，大家都笑了。'
        if '工作' in topic:
            return '那我给您讲个小故事：有位阿姨退休后常想起以前上班的那条老街。她有天又去走了一圈，发现面馆还在，老板一眼就认出了她，还笑着说，您精神头还是和从前一样。'
        return '那我给您讲个小故事：有位奶奶每天早上都把窗户轻轻推开，让阳光先进屋。她总说，日子慢一点没关系，只要心里亮堂，今天就会过得稳稳当当。'

    def _preferred_topic(self, context: dict[str, Any]) -> str:
        profile = context.get('profile') or {}
        if not isinstance(profile, dict):
            return ''
        stable_profile = profile.get('stable_profile') or {}
        if not isinstance(stable_profile, dict):
            return ''
        liked_topics = stable_profile.get('liked_topics') or []
        if not isinstance(liked_topics, list):
            return ''
        for item in liked_topics:
            topic = str(item).strip()
            if topic:
                return topic
        return ''

    def _is_medication_confirmation_text(self, text: str) -> bool:
        normalized = text.strip()
        direct_matches = [
            '吃过药',
            '已经吃药',
            '药吃了',
            '刚吃了药',
            '药都吃了',
            '药都吃好了',
            '药都吃完了',
            '两个药都吃了',
            '两个药都吃好了',
            '两个药都吃完了',
            '两种药都吃了',
            '两种药都吃好了',
            '两种药都吃完了',
        ]
        if any(token in normalized for token in direct_matches):
            return True
        medication_confirmation_patterns = [
            r'药[^。；，,\n]{0,8}(吃好了|吃完了|吃了|服好了|服完了)',
            r'(吃好了|吃完了|吃了|服好了|服完了)[^。；，,\n]{0,8}药',
        ]
        return any(re.search(pattern, normalized) for pattern in medication_confirmation_patterns)
