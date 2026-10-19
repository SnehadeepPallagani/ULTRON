import json
import os
import urllib.request

import urllib.error
from pathlib import Path

from datetime import datetime

from director import UltronDirector

from research import conduct_research

try:
    from vibe_coding_engine import VibeCodingEngine
except ImportError:
    VibeCodingEngine = None

try:

    from context_engine import ContextEngine

except ImportError:

    ContextEngine = None

class ULTRONCore:

    def __init__(self):

        self.director = UltronDirector()

        self.context_engine = (

            ContextEngine()

            if ContextEngine

            else None

        )

        self.ollama_url = (

            "http://localhost:11434/api/generate"

        )

        self.conversation_history = []

                # -----------------------------------------------------
        # Vibe Coding Engine — isolated project workspace
        # -----------------------------------------------------
        if VibeCodingEngine:
            workspace = Path(
                os.environ.get(
                    "ULTRON_PROJECT_ROOT",
                    str(Path.home() / "ULTRON_Workspace")
                )
            ).expanduser().resolve()

            source_root = Path(__file__).resolve().parent

            # Never allow generated projects to overlap ULTRON's source.
            if (
                workspace == source_root
                or workspace in source_root.parents
                or source_root in workspace.parents
            ):
                raise ValueError(
                    "ULTRON_PROJECT_ROOT must be separate from "
                    "the ULTRON source directory."
                )

            workspace.mkdir(parents=True, exist_ok=True)

            self.vibe_coding_engine = VibeCodingEngine(
                project_root=workspace
            )
        else:
            self.vibe_coding_engine = None
        

        # -----------------------------------------------------

        # Canonical concept knowledge.

        #

        # These are high-confidence meanings that ULTRON must

        # not reinterpret through self-referential prompting.

        # -----------------------------------------------------

        self.concept_knowledge = {

            "vibecoding": """

Vibecoding is an AI-assisted software development

approach in which a developer describes desired software,

features, behavior, or changes using natural language and

an AI coding system generates or modifies the implementation.

The developer remains responsible for directing the work,

reviewing the generated implementation, testing it,

finding problems, and iterating with the AI.

Vibecoding is commonly associated with rapid,

iterative, conversational software development.

It is not a formal programming language or framework.

""",

            "vibe coding": """

Vibe coding is an AI-assisted software development

approach where a developer communicates desired software

behavior and changes in natural language and an AI coding

system generates or modifies code.

The developer guides the process and should review,

test, verify, and refine the resulting software.

It is not a programming language or formal framework.

"""

        }

    # =========================================================

    # CONCEPT KNOWLEDGE

    # =========================================================

    def get_concept_knowledge(

        self,

        user_input

    ):

        text = user_input.lower().strip()

        # -----------------------------------------------------

        # Exact concept detection

        # -----------------------------------------------------

        if (

            "what is vibecoding" in text

            or "what is vibe coding" in text

            or "define vibecoding" in text

            or "define vibe coding" in text

        ):

            return self.concept_knowledge[

                "vibecoding"

            ]

        return None

    # =========================================================

    # CONTEXT

    # =========================================================

    def understand(

        self,

        user_input

    ):

        if self.context_engine:

            return self.context_engine.analyze(

                user_input,

                self.conversation_history

            )

        text = user_input.lower().strip()

        if (

            "can you" in text

            or "could you" in text

            or "are you able" in text

        ):

            intent = "capability_question"

            task_type = "capability"

        elif (

            text.startswith("what is")

            or text.startswith("what are")

            or text.startswith("explain")

            or text.startswith("define")

        ):

            intent = "explanation"

            task_type = "explanation"

        elif (

            "vibecode" in text

            or "build" in text

            or "create" in text

            or "develop" in text

        ):

            intent = "software_task"

            task_type = "software_creation"

        else:

            intent = "general"

            task_type = "question_answering"

        return {

            "original_request":

                user_input,

            "intent":

                intent,

            "task_type":

                task_type,

            "domain":

                "software"

                if any(

                    x in text

                    for x in [

                        "code",

                        "coding",

                        "software",

                        "website",

                        "vibecode",

                        "program"

                    ]

                )

                else "general",

            "action":

                (

                    "answer"

                    if intent

                    in {

                        "capability_question",

                        "explanation"

                    }

                    else "create"

                ),

            "artifact":

                None,

            "reference": {

                "present":

                    False,

                "resolved":

                    None

            },

            "capability_question":

                intent == "capability_question",

            "confidence":

                0.70,

            "clarification_needed":

                False

        }

    # =========================================================

    # DIRECTOR PLAN

    # =========================================================

    def create_plan(

        self,

        user_input,

        context

    ):

        intent = context.get(

            "intent",

            "general"

        )

        task_type = context.get(

            "task_type",

            "question_answering"

        )

        domain = context.get(

            "domain",

            "general"

        )

        action = context.get(

            "action",

            "answer"

        )

        artifact = context.get(

            "artifact"

        )

        # -----------------------------------------------------

        # Deterministic Director

        # -----------------------------------------------------

        plan = self.director.rule_analyze(

            user_input

        )

        # -----------------------------------------------------

        # Capability question

        # -----------------------------------------------------

        if intent == "capability_question":

            plan.update({

                "intent":

                    "capability_question",

                "domain":

                    domain,

                "current_information":

                    False,

                "web_required":

                    False,

                "images_required":

                    False,

                "complexity":

                    "low",

                "research_depth":

                    "none",

                "recommended_brain":

                    "velocity",

                "tools_required":

                    [],

                "output_format":

                    "paragraph"

            })

        # -----------------------------------------------------

        # Explanation

        # -----------------------------------------------------

        elif intent == "explanation":

            plan.update({

                "intent":

                    "explanation",

                "domain":

                    domain,

                "current_information":

                    False,

                "web_required":

                    False,

                "images_required":

                    False,

                "complexity":

                    "low",

                "research_depth":

                    "none",

                "recommended_brain":

                    "velocity",

                "tools_required":

                    [],

                "output_format":

                    "mixed"

            })

        # -----------------------------------------------------

        # Software creation

        # -----------------------------------------------------

        elif task_type == "software_creation":

            plan.update({

                "intent":

                    "coding",

                "domain":

                    "programming",

                "recommended_brain":

                    "forge",

                "output_format":

                    "mixed",

                "execution_mode":

                    "vibe_coding"

            })

        # -----------------------------------------------------

        # Software modification

        # -----------------------------------------------------

        elif task_type in {

            "software_modification",

            "artifact_modification"

        }:

            plan.update({

                "intent":

                    "coding",

                "domain":

                    "programming",

                "recommended_brain":

                    "forge",

                "output_format":

                    "mixed",

                "execution_mode":

                    "vibe_coding"

            })

        # -----------------------------------------------------

        # Research

        # -----------------------------------------------------

        elif intent == "research":

            plan["intent"] = "research"

        # -----------------------------------------------------

        # Context metadata

        # -----------------------------------------------------

        plan[

            "context_contract"

        ] = context

        plan[

            "context_task_type"

        ] = task_type

        plan[

            "context_action"

        ] = action

        plan[

            "context_artifact"

        ] = artifact

        # -----------------------------------------------------

        # Capability routing

        # -----------------------------------------------------

        plan[

            "required_capability_level"

        ] = self.director.determine_required_level(

            plan

        )

        plan[

            "brain_route"

        ] = self.director.route_brain(

            plan

        )

        return plan

    # =========================================================

    # RESEARCH

    # =========================================================

    def perform_research(

        self,

        user_input,

        plan

    ):

        if not plan.get(

            "web_required",

            False

        ):

            return {

                "required":

                    False,

                "success":

                    True,

                "context":

                    "",

                "results":

                    []

            }

        result = conduct_research(

            user_input

        )

        results = result.get(

            "results",

            []

        )

        success = result.get(

            "success",

            False

        )

        return {

            "required":

                True,

            "success":

                success and bool(results),

            "context":

                result.get(

                    "context",

                    ""

                ),

            "results":

                results,

            "queries":

                result.get(

                    "queries",

                    []

                )

        }

    # =========================================================

    # BRAIN CALL

    # =========================================================

    def call_brain(

        self,

        user_input,

        plan,

        research_context="",

        concept_context=None

    ):

        brain_route = plan[

            "brain_route"

        ]

        model = brain_route[

            "model"

        ]

        context = plan.get(

            "context_contract",

            {}

        )

        history = (

            self.conversation_history[-10:]

        )

        history_text = "\n".join(

            f"{item.get('role', '').upper()}: "

            f"{item.get('content', '')}"

            for item in history

        )

        current_date = (

            datetime.now().strftime(

                "%Y-%m-%d"

            )

        )

        system_prompt = f"""

You are ULTRON, a personal AI system created,

designed, developed, and architected by

Snehadeep Pallagani.

CURRENT DATE:

{current_date}

You must understand the user's actual request before

responding.

ULTRON TASK CONTRACT:

{json.dumps(context, indent=2)}

EXECUTION PLAN:

{json.dumps(plan, indent=2)}

CORE RULES:

1. Understand before acting.

2. A capability question is NOT an execution request.

3. An explanation question is NOT an execution request.

4. Never invent the meaning of a term.

5. Never confuse a concept with ULTRON's own capabilities.

6. Never invent requirements.

7. Never impose a framework, language, library,

   architecture, or design without justification.

8. If the user asks whether ULTRON can do something,

   answer the capability question directly.

9. If the user asks what something means,

   explain the concept directly.

10. If the user requests software creation,

    treat it as a real software-development task.

11. If the user requests modification of an existing

    artifact, preserve its existing functionality.

12. Do not claim an artifact was modified if ULTRON

    did not actually access and modify it.

13. Do not claim software works unless it has actually

    been tested or verified.

14. Do not fabricate sources, statistics, URLs,

    quotations, dates, or current events.

15. Do not repeatedly address the user as Sir.

16. Give useful, complete answers without unnecessary filler.

17. Do not mention internal model routing unless asked.

18. For software tasks, follow:

    understand → inspect → plan → build/edit →

    run → test → fix → verify.

19. If an existing artifact is required but unavailable,

    clearly say that the artifact must be provided or

    located before modification.

20. Vibecoding means AI-assisted software development

    driven through natural-language instructions and

    iterative generation/modification, with the developer

    guiding, reviewing, testing, and refining the result.

"""

        if concept_context:

            system_prompt += f"""

AUTHORITATIVE CONCEPT CONTEXT:

{concept_context}

Use this definition when answering the current concept

question. Do not replace it with a self-referential

definition.

"""

        if research_context:

            system_prompt += f"""

WEB RESEARCH:

{research_context}

Use this evidence for current/research claims.

"""

        system_prompt += f"""

RECENT CONVERSATION:

{history_text}

"""

        prompt = f"""

{system_prompt}

USER REQUEST:

{user_input}

Provide the best answer now.

"""

        payload = {

            "model":

                model,

            "prompt":

                prompt,

            "stream":

                False

        }

        data = json.dumps(

            payload

        ).encode("utf-8")

        request = urllib.request.Request(

            self.ollama_url,

            data=data,

            headers={

                "Content-Type":

                    "application/json"

            },

            method="POST"

        )

        try:

            with urllib.request.urlopen(

                request,

                timeout=120

            ) as response:

                result = json.loads(

                    response.read().decode(

                        "utf-8"

                    )

                )

            answer = result.get(

                "response",

                ""

            ).strip()

            if not answer:

                return (

                    "I didn't receive a response "

                    "from the selected ULTRON brain."

                )

            return answer

        except urllib.error.URLError as error:

            return (

                f"ULTRON connection error: {error}"

            )

        except TimeoutError:

            return (

                "The selected ULTRON brain timed out."

            )

    # =========================================================

    # PRECONDITION CHECK

    # =========================================================

    # =========================================================
    # VIBE CODING EXECUTION
    # =========================================================

    def execute_vibe_coding(
        self,
        user_input,
        context,
        plan,
    ):
        """
        Execute real project operations through the Vibe Coding Engine.

        ULTRON only reports an edit as successful when the underlying
        engine has actually changed or verified the target.
        """

        if not self.vibe_coding_engine:
            return {
                "handled": False,
                "success": False,
                "status": "ENGINE_UNAVAILABLE",
                "answer": (
                    "The Vibe Coding Engine is not available."
                ),
            }

        analysis = self.vibe_coding_engine.analyze_request(
            user_input
        )

        action = analysis.get("action")
        target = analysis.get("target")

        # -----------------------------------------------------
        # "Vibecode this website."
        # Inspect the existing project first. Do not regenerate it.
        # -----------------------------------------------------

        if (
            action == "inspect_and_modify"
            and target == "website"
        ):
            inspection = (
                self.vibe_coding_engine.inspect_website()
            )

            if not inspection.get("success"):
                return {
                    "handled": True,
                    "success": False,
                    "status": "PROJECT_INSPECTION_FAILED",
                    "answer": (
                        "I couldn't inspect the existing website, "
                        "so I won't claim that it was modified."
                    ),
                    "result": inspection,
                }

            sections = (
                inspection.get("structure", {})
                .get("sections", {})
            )

            detected = [
                name
                for name, present in sections.items()
                if present
            ]

            return {
                "handled": True,
                "success": True,
                "status": "PROJECT_INSPECTED",
                "answer": (
                    f"I inspected the existing website at "
                    f"{inspection['relative_path']}. "
                    f"It contains {inspection['lines']} lines. "
                    f"Detected structure: {', '.join(detected)}. "
                    "The project is ready for targeted edits."
                ),
                "result": inspection,
            }

        # -----------------------------------------------------
        # "Add Create Account to the same HTML."
        # Perform the real targeted modification.
        # -----------------------------------------------------

        if (
            action == "modify"
            and target == "create_account"
        ):
            result = (
                self.vibe_coding_engine.add_create_account(
                    dry_run=False
                )
            )

            if result.success:
                if result.changed:
                    answer = (
                        "Done. I modified the existing HTML, "
                        "created a backup, and verified the result."
                    )
                else:
                    answer = (
                        "The existing HTML already contains "
                        "a Create Account element, so I did not "
                        "add a duplicate."
                    )

                return {
                    "handled": True,
                    "success": True,
                    "status": "VIBE_EDIT_VERIFIED",
                    "answer": answer,
                    "result": result,
                }

            return {
                "handled": True,
                "success": False,
                "status": "VIBE_EDIT_FAILED",
                "answer": (
                    "I couldn't safely complete that modification. "
                    f"{result.message}"
                ),
                "result": result,
            }

        # -----------------------------------------------------
        # Generic software modification
        # Route real modification requests through the Vibe
        # Coding Engine instead of answering with instructions.
        # The engine performs inspection, targeted patching,
        # backup, validation, and verification.
        # -----------------------------------------------------

        if action == "modify":
            result = self.vibe_coding_engine.modify_project(
                user_input,
                dry_run=False
            )

            if result.success:
                if result.changed:
                    answer = (
                        "Done. I modified the existing project, "
                        "created a backup, and verified the result."
                    )
                else:
                    answer = (
                        "I inspected the existing project, but no "
                        "change was necessary."
                    )

                return {
                    "handled": True,
                    "success": True,
                    "status": "VIBE_EDIT_VERIFIED",
                    "answer": answer,
                    "result": result,
                }

            return {
                "handled": True,
                "success": False,
                "status": "VIBE_EDIT_FAILED",
                "answer": (
                    "I couldn't safely complete that modification. "
                    f"{result.message}"
                ),
                "result": result,
            }

        return {
            "handled": False,
            "success": False,
            "status": "NOT_HANDLED",
            "answer": "",
            "result": analysis,
        }

    def check_task_preconditions(

        self,

        context

    ):

        task_type = context.get(

            "task_type"

        )

        artifact = context.get(

            "artifact"

        )

        reference = context.get(

            "reference",

            {}

        )

        # -----------------------------------------------------

        # Software modification

        # -----------------------------------------------------

        if task_type in {

            "software_modification",

            "artifact_modification"

        }:

            resolved = (

                reference.get(

                    "resolved"

                )

                if reference

                else None

            )

            if not artifact and not resolved:

                return {

                    "ready":

                        False,

                    "reason":

                        "existing_artifact_required"

                }

        return {

            "ready":

                True,

            "reason":

                None

        }

    # =========================================================

    # MAIN PROCESS

    # =========================================================

    def process(

        self,

        user_input

    ):

        user_input = (

            user_input or ""

        ).strip()

        if not user_input:

            return {

                "answer":

                    "Please provide a request.",

                "plan":

                    {},

                "research":

                    None

            }

        # =====================================================

        # 1. UNDERSTAND

        # =====================================================

        context = self.understand(

            user_input

        )

        # =====================================================

        # 2. AUTHORITATIVE CONCEPT

        # =====================================================

        concept_context = (

            self.get_concept_knowledge(

                user_input

            )

        )

        # =====================================================

        # 3. PRECONDITIONS

        # =====================================================

        preconditions = (

            self.check_task_preconditions(

                context

            )

        )

        # -----------------------------------------------------

        # Missing artifact

        # -----------------------------------------------------

        if not preconditions["ready"]:

            artifact = context.get(

                "artifact"

            )

            reference = context.get(

                "reference",

                {}

            )

            if (

                artifact

                or reference.get(

                    "resolved"

                )

            ):

                answer = (

                    "I can make that modification, but I "

                    "need access to the existing artifact "

                    "first. Provide the HTML/project or "

                    "make the existing file available to "

                    "ULTRON, and I'll inspect it before "

                    "changing anything."

                )

                self._remember(

                    user_input,

                    answer

                )

                return {

                    "answer":

                        answer,

                    "plan": {

                        "context_contract":

                            context,

                        "status":

                            "ARTIFACT_REQUIRED"

                    },

                    "research":

                        None

                }

        # =====================================================

        # 4. PLAN

        # =====================================================

        plan = self.create_plan(

            user_input,

            context

        )

        # =====================================================

        # =====================================================
        # 5. VIBE CODING EXECUTION
        # =====================================================

        if plan.get("execution_mode") == "vibe_coding":
            vibe_result = self.execute_vibe_coding(
                user_input,
                context,
                plan
            )

            if vibe_result.get("handled"):
                plan["status"] = vibe_result.get(
                    "status",
                    "VIBE_CODING"
                )

                plan["vibe_coding"] = vibe_result

                answer = vibe_result.get(
                    "answer",
                    ""
                )

                self._remember(
                    user_input,
                    answer
                )

                return {
                    "answer": answer,
                    "plan": plan,
                    "research": None,
                }

        # 5. CONCEPT ANSWER

        # =====================================================

        if concept_context:

            # Explanation questions can be answered directly

            # with authoritative concept context.

            if context.get(

                "intent"

            ) == "explanation":

                answer = self.call_brain(

                    user_input,

                    plan,

                    "",

                    concept_context

                )

                self._remember(

                    user_input,

                    answer

                )

                plan["status"] = (

                    "COMPLETED"

                )

                return {

                    "answer":

                        answer,

                    "plan":

                        plan,

                    "research":

                        None

                }

        # =====================================================

        # 6. RESEARCH

        # =====================================================

        research = self.perform_research(

            user_input,

            plan

        )

        if (

            research["required"]

            and not research["success"]

        ):

            answer = (

                "I couldn't obtain reliable web sources "

                "for this request right now, so I won't "

                "present an unverified current answer."

            )

            self._remember(

                user_input,

                answer

            )

            plan["status"] = (

                "RESEARCH_UNAVAILABLE"

            )

            return {

                "answer":

                    answer,

                "plan":

                    plan,

                "research":

                    research

            }

        # =====================================================

        # 7. BRAIN

        # =====================================================

        answer = self.call_brain(

            user_input,

            plan,

            research.get(

                "context",

                ""

            ),

            concept_context

        )

        # =====================================================

        # 8. MEMORY

        # =====================================================

        self._remember(

            user_input,

            answer

        )

        plan["status"] = (

            "COMPLETED"

        )

        return {

            "answer":

                answer,

            "plan":

                plan,

            "research":

                research

        }

    # =========================================================

    # MEMORY

    # =========================================================

    def _remember(

        self,

        user_input,

        answer

    ):

        self.conversation_history.append({

            "role":

                "user",

            "content":

                user_input

        })

        self.conversation_history.append({

            "role":

                "assistant",

            "content":

                answer

        })

        if len(

            self.conversation_history

        ) > 40:

            self.conversation_history = (

                self.conversation_history[-40:]

            )

# =============================================================

# TEST

# =============================================================

if __name__ == "__main__":

    print()

    print("=" * 70)

    print("ULTRON CORE")

    print("=" * 70)

    print(

        "Context → Contract → Director → "

        "Research → Brain"

    )

    print()

    core = ULTRONCore()

    tests = [

        "Can you vibecode?",

        "What is vibecoding?",

        "Vibecode this website.",

        "Add Create Account to the same HTML.",

        "Make the navbar better.",

        "What is an operating system?",

        "Write Python code to reverse a string."

    ]

    for request in tests:

        print()

        print("=" * 70)

        print(

            "USER:",

            request

        )

        print("=" * 70)

        result = core.process(

            request

        )

        plan = result.get(

            "plan",

            {}

        )

        context = plan.get(

            "context_contract",

            {}

        )

        route = plan.get(

            "brain_route",

            {}

        )

        print(

            "\nINTENT:",

            context.get(

                "intent"

            )

        )

        print(

            "TASK:",

            context.get(

                "task_type"

            )

        )

        print(

            "ACTION:",

            context.get(

                "action"

            )

        )

        print(

            "ARTIFACT:",

            context.get(

                "artifact"

            )

        )

        print(

            "BRAIN:",

            route.get(

                "brain"

            )

        )

        print(

            "\nULTRON:"

        )

        print(

            result.get(

                "answer",

                ""

            )

        )
