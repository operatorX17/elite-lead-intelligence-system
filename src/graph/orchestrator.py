'''
LangGraph Orchestrator for ZRAI Lead OS.
'''

from typing import Dict, Any, Optional, List, Literal
from datetime import datetime
from uuid import UUID
import logging
import os
import functools

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, interrupt

from src.graph.state import LeadGraphState
from src.config import load_config
from src.db.client import get_supabase_client

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_DELAY_MS = 1000


def create_checkpointer(mode: str = 'production'):
    if mode == 'testing':
        return InMemorySaver()
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        db_path = os.getenv('LANGGRAPH_CHECKPOINT_DB', 'checkpoints/langgraph.db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        return SqliteSaver.from_conn_string(db_path)
    except ImportError:
        return InMemorySaver()


def with_retry(max_retries=MAX_RETRIES, base_delay_ms=BASE_DELAY_MS):
    def decorator(node_func):
        @functools.wraps(node_func)
        def wrapper(state):
            node_name = node_func.__name__
            retry_key = f'{node_name}_retry_count'
            metadata = state.get('metadata', {}) or {}
            retry_count = metadata.get(retry_key, 0)
            try:
                return node_func(state)
            except Exception as e:
                if retry_count < max_retries:
                    return Command(update={'metadata': {retry_key: retry_count + 1}, 'errors': [{'node': node_name, 'error': str(e)}]}, goto=node_name)
                return Command(update={'errors': [{'node': node_name, 'error': str(e), 'fatal': True}]}, goto='handle_error')
        return wrapper
    return decorator


def discovery_node(state):
    return {'current_stage': 'discovery', 'last_node': 'discovery'}


def enrichment_node(state):
    return {'current_stage': 'enrichment', 'last_node': 'enrichment'}


def intent_node(state):
    return Command(update={'intent': {'intent_score': 75, 'leak_score': 50}, 'current_stage': 'intent', 'last_node': 'intent'}, goto='governance')


def governance_node(state):
    config = load_config()
    db = get_supabase_client()
    metrics = db.get_or_create_usage_metrics(datetime.utcnow())
    intent_data = state.get('intent', {}) or {}
    leak_score = intent_data.get('leak_score', 0)
    budget_exceeded = metrics.get('browser_sessions_used', 0) >= config.budget.daily_browser_session_limit
    if budget_exceeded or leak_score < 70 or state.get('should_skip_audit', False):
        return Command(update={'should_skip_audit': True, 'current_stage': 'governance', 'last_node': 'governance'}, goto='scoring')
    return Command(update={'current_stage': 'governance', 'last_node': 'governance'}, goto='audit')


@with_retry(max_retries=2, base_delay_ms=5000)
def audit_node(state):
    return Command(update={'proof': {'screenshots': [], 'audit_bullets': []}, 'current_stage': 'audit', 'last_node': 'audit'}, goto='scoring')


def scoring_node(state):
    update = {'scoring': {'final_score': 75, 'lead_tier': 'B', 'do_not_contact': False}, 'is_disqualified': False, 'current_stage': 'scoring', 'last_node': 'scoring'}
    return Command(update=update, goto='outreach')


def outreach_node(state):
    return {'outreach_messages': [{'channel': 'email', 'subject': 'Hi'}], 'requires_approval': True, 'approval_status': 'pending', 'current_stage': 'outreach', 'last_node': 'outreach'}


def approval_node(state):
    approval_response = interrupt({'question': 'Approve?', 'messages': state.get('outreach_messages', [])})
    return {'approval_status': approval_response.get('status', 'rejected'), 'approval_notes': approval_response.get('notes', '')}


def send_outreach_node(state):
    if state.get('approval_status') != 'approved':
        return Command(update={'errors': [{'node': 'send_outreach', 'error': 'Not approved'}]}, goto='end')
    return Command(update={'metadata': {'messages_sent': True}, 'current_stage': 'sent'}, goto='conversation')


def conversation_node(state):
    if state.get('is_escalated'):
        return Command(update={'is_escalated': True, 'current_stage': 'conversation', 'last_node': 'conversation'}, goto='escalate')
    return Command(update={'current_stage': 'conversation', 'last_node': 'conversation'}, goto='end')


def escalate_node(state):
    db = get_supabase_client()
    lead_id = state.get('lead_id')
    if lead_id:
        db.update_lead(lead_id, {'lead_lifecycle_state': 'QUALIFIED', 'updated_at': datetime.utcnow().isoformat()})
    return {'is_complete': True, 'current_stage': 'escalated', 'last_node': 'escalate'}


def handle_error_node(state):
    return {'is_complete': True, 'current_stage': 'error', 'last_node': 'handle_error'}


def end_node(state):
    return {'is_complete': True, 'current_stage': 'complete', 'last_node': 'end'}


def build_lead_graph(checkpointer=None, enable_approval=True):
    graph = StateGraph(LeadGraphState)
    graph.add_node('discovery', discovery_node)
    graph.add_node('enrichment', enrichment_node)
    graph.add_node('intent', intent_node)
    graph.add_node('governance', governance_node)
    graph.add_node('audit', audit_node)
    graph.add_node('scoring', scoring_node)
    graph.add_node('outreach', outreach_node)
    graph.add_node('approval', approval_node)
    graph.add_node('send_outreach', send_outreach_node)
    graph.add_node('conversation', conversation_node)
    graph.add_node('escalate', escalate_node)
    graph.add_node('handle_error', handle_error_node)
    graph.add_node('end', end_node)
    graph.add_edge(START, 'discovery')
    graph.add_edge('discovery', 'enrichment')
    graph.add_edge('enrichment', 'intent')
    graph.add_edge('audit', 'scoring')
    graph.add_edge('outreach', 'approval')
    graph.add_edge('approval', 'send_outreach')
    graph.add_edge('escalate', 'end')
    graph.add_edge('handle_error', 'end')
    graph.add_edge('end', END)
    interrupt_before = ['approval'] if enable_approval else []
    return graph.compile(checkpointer=checkpointer, interrupt_before=interrupt_before)


class LeadOrchestrator:
    def __init__(self, mode='production'):
        self._config = load_config()
        self._db = get_supabase_client()
        self._checkpointer = create_checkpointer(mode)
        self._graph = build_lead_graph(self._checkpointer)
        self._logger = logging.getLogger('zrai.orchestrator')
    
    def _load_lead_from_db(self, lead_id):
        lead_data = self._db.get_lead(lead_id)
        if not lead_data:
            return None
        return {'lead_id': lead_data.get('lead_id'), 'business_name': lead_data.get('business_name', 'Unknown')}
    
    def _create_initial_state(self, lead_id, lead_data=None):
        return {'lead_id': lead_id, 'thread_id': str(lead_id), 'lead': lead_data, 'current_stage': 'start', 'last_node': 'start', 'enrichment': {}, 'intent': {}, 'scoring': {}, 'proof': {}, 'outreach_messages': [], 'conversation_transcript': [], 'conversation_entities': {}, 'errors': [], 'retry_count': 0, 'should_skip_audit': False, 'should_skip_outreach': False, 'is_disqualified': False, 'is_escalated': False, 'is_complete': False, 'requires_approval': False, 'approval_status': None, 'approval_notes': None, 'metadata': {}, 'messages': []}
    
    def process_lead(self, lead_id, config_override=None):
        if self._config.kill_switches.global_kill:
            raise RuntimeError('Global kill switch is active')
        lead_data = self._load_lead_from_db(lead_id)
        initial_state = self._create_initial_state(lead_id, lead_data)
        if config_override:
            initial_state['metadata']['config_override'] = config_override
        config = {'configurable': {'thread_id': str(lead_id)}}
        return self._graph.invoke(initial_state, config)
    
    def resume_lead(self, lead_id, resume_value=None):
        config = {'configurable': {'thread_id': str(lead_id)}}
        if resume_value is not None:
            return self._graph.invoke(Command(resume=resume_value), config)
        return self._graph.invoke(None, config)
    
    def dry_run(self, lead_id):
        lead_data = self._load_lead_from_db(lead_id)
        initial_state = self._create_initial_state(lead_id, lead_data)
        initial_state['metadata']['dry_run'] = True
        config = {'configurable': {'thread_id': f'{lead_id}_dry_run'}}
        return self._graph.invoke(initial_state, config)
    
    def get_state(self, lead_id):
        config = {'configurable': {'thread_id': str(lead_id)}}
        state_snapshot = self._graph.get_state(config)
        if state_snapshot:
            return {'values': state_snapshot.values, 'next': state_snapshot.next, 'metadata': state_snapshot.metadata}
        return None
    
    def get_graph_mermaid(self):
        return self._graph.get_graph().draw_mermaid()


def create_orchestrator(mode='production'):
    return LeadOrchestrator(mode=mode)
