import re


class ContextEngine:
    """
    ULTRON Context + Intent Intelligence

    Purpose:
    - Understand the user's request before execution.
    - Resolve conversational references.
    - Distinguish capability questions from action requests.
    - Recognize software/vibecoding requests.
    - Recognize existing-project modification requests.
    - Provide a structured task contract to the Director.

    Priority rule:
        CURRENT REQUEST
            >
        EXPLICIT ARTIFACT
            >
        CONVERSATION CONTEXT
            >
        DEFAULT ASSUMPTION
    """

    def __init__(self):
        self.last_topic = None
        self.last_artifact = None
        self.last_task = None

    # =========================================================
    # MAIN ENTRY
    # =========================================================

    def analyze(self, user_input, conversation_history=None):

        text = (user_input or "").strip()
        lower = text.lower()

        history = conversation_history or []

        intent = self.detect_intent(lower)
        domain = self.detect_domain(lower)

        explicit_artifact = self.detect_artifact(lower)

        reference = self.resolve_reference(
            text,
            lower,
            history,
            explicit_artifact
        )

        artifact = (
            explicit_artifact
            if explicit_artifact
            else reference.get("resolved")
        )

        action = self.detect_action(
            lower,
            intent
        )

        task_type = self.determine_task_type(
            intent,
            action,
            artifact
        )

        confidence = self.calculate_confidence(
            lower,
            intent,
            domain,
            action,
            artifact
        )

        capability_question = (
            intent == "capability_question"
        )

        clarification_needed = (
            confidence < 0.45
            and intent not in {
                "capability_question",
                "greeting"
            }
        )

        contract = {
            "original_request": text,

            "intent": intent,

            "task_type": task_type,

            "domain": domain,

            "action": action,

            "artifact": artifact,

            "reference": reference,

            "capability_question": capability_question,

            "confidence": round(
                confidence,
                2
            ),

            "clarification_needed": clarification_needed,

            "understanding": self.build_understanding(
                text,
                intent,
                task_type,
                domain,
                action,
                artifact,
                reference
            )
        }

        self.update_state(contract)

        return contract

    # =========================================================
    # INTENT DETECTION
    # =========================================================

    def detect_intent(self, text):

        # -----------------------------------------------------
        # Greeting
        # -----------------------------------------------------

        if re.fullmatch(
            r"(hi|hello|hey|hey there|good morning|good evening|good afternoon)[!. ]*",
            text
        ):
            return "greeting"

        # -----------------------------------------------------
        # Capability questions
        # -----------------------------------------------------

        capability_patterns = [

            r"\bcan you\b",

            r"\bcould you\b",

            r"\bare you able to\b",

            r"\bdo you support\b",

            r"\bdo you know how to\b",

            r"\bcan ultron\b",

            r"\bwhat can you do\b",

            r"\bare you capable of\b",

            r"\bdo you have the ability\b"
        ]

        if any(
            re.search(pattern, text)
            for pattern in capability_patterns
        ):
            return "capability_question"

        # -----------------------------------------------------
        # Definition / explanation
        # -----------------------------------------------------

        explanation_patterns = [

            r"^what is\b",

            r"^what are\b",

            r"^who is\b",

            r"^why is\b",

            r"^why are\b",

            r"^how does\b",

            r"^how do\b",

            r"^explain\b",

            r"^define\b",

            r"^tell me about\b"
        ]

        if any(
            re.search(pattern, text)
            for pattern in explanation_patterns
        ):
            return "explanation"

        # -----------------------------------------------------
        # Software / building
        # -----------------------------------------------------

        coding_patterns = [

            r"\bwrite\b.*\bcode\b",

            r"\bcreate\b.*\bwebsite\b",

            r"\bbuild\b.*\bwebsite\b",

            r"\bmake\b.*\bwebsite\b",

            r"\bdevelop\b",

            r"\bcode\b",

            r"\bprogram\b",

            r"\bimplement\b",

            r"\bcreate an app\b",

            r"\bbuild an app\b",

            r"\bcreate a tool\b",

            r"\bbuild a tool\b",

            r"\bvibecode\b",

            r"\bvibecoding\b"
        ]

        if any(
            re.search(pattern, text)
            for pattern in coding_patterns
        ):
            return "software_task"

        # -----------------------------------------------------
        # Modification
        # -----------------------------------------------------

        modification_patterns = [

            r"\badd\b",

            r"\bremove\b",

            r"\bdelete\b",

            r"\bchange\b",

            r"\bmodify\b",

            r"\bupdate\b",

            r"\bfix\b",

            r"\bimprove\b",

            r"\bupgrade\b",

            r"\bredesign\b",

            r"\bedit\b",

            r"\bmake .* better\b"
        ]

        if any(
            re.search(pattern, text)
            for pattern in modification_patterns
        ):
            return "modification"

        # -----------------------------------------------------
        # Research
        # -----------------------------------------------------

        research_patterns = [

            r"\bresearch\b",

            r"\binvestigate\b",

            r"\banalyze\b",

            r"\bcompare\b",

            r"\blatest\b",

            r"\bcurrent\b",

            r"\brecent\b",

            r"\bnews\b"
        ]

        if any(
            re.search(pattern, text)
            for pattern in research_patterns
        ):
            return "research"

        # -----------------------------------------------------
        # Question
        # -----------------------------------------------------

        if text.endswith("?"):
            return "question"

        return "general"

    # =========================================================
    # DOMAIN DETECTION
    # =========================================================

    def detect_domain(self, text):

        domains = {

            "software": [
                "code",
                "coding",
                "program",
                "programming",
                "website",
                "web app",
                "webpage",
                "application",
                "html",
                "css",
                "javascript",
                "python",
                "java",
                "react",
                "api",
                "backend",
                "frontend",
                "vibecode",
                "vibecoding",
                "navbar",
                "login page"
            ],

            "ai": [
                "ai",
                "artificial intelligence",
                "llm",
                "machine learning",
                "deep learning",
                "neural network",
                "agent",
                "model",
                "ai tool"
            ],

            "hardware": [
                "arduino",
                "esp32",
                "sensor",
                "microcontroller",
                "electronics",
                "circuit"
            ],

            "academic": [
                "exam",
                "assignment",
                "lab",
                "experiment",
                "semester",
                "subject",
                "question"
            ],

            "science": [
                "physics",
                "chemistry",
                "biology",
                "scientific",
                "medical",
                "medicine"
            ],

            "business": [
                "business",
                "startup",
                "marketing",
                "finance",
                "customer",
                "sales"
            ]
        }

        scores = {}

        for domain, keywords in domains.items():

            score = 0

            for keyword in keywords:

                if keyword in text:
                    score += 1

            if score:
                scores[domain] = score

        if not scores:
            return "general"

        return max(
            scores,
            key=scores.get
        )

    # =========================================================
    # ACTION DETECTION
    # =========================================================

    def detect_action(self, text, intent):

        # -----------------------------------------------------
        # Capability questions are NOT actions.
        # They require an answer about ULTRON's capability.
        # -----------------------------------------------------

        if intent == "capability_question":
            return "answer"

        # -----------------------------------------------------
        # Explanation
        # -----------------------------------------------------

        if intent == "explanation":

            return "explain"

        # -----------------------------------------------------
        # Explicit modification verbs
        # Check these BEFORE generic create/build verbs.
        # -----------------------------------------------------

        modification_words = [
            "add",
            "remove",
            "delete",
            "change",
            "modify",
            "update",
            "fix",
            "improve",
            "upgrade",
            "redesign",
            "edit"
        ]

        if any(
            re.search(
                rf"\b{re.escape(word)}\b",
                text
            )
            for word in modification_words
        ):
            return "modify"

        # -----------------------------------------------------
        # "make X better"
        # -----------------------------------------------------

        if re.search(
            r"\bmake\b.*\bbetter\b",
            text
        ):
            return "modify"

        # -----------------------------------------------------
        # Creation
        # -----------------------------------------------------

        creation_words = [
            "build",
            "create",
            "develop",
            "generate",
            "vibecode"
        ]

        if any(
            re.search(
                rf"\b{re.escape(word)}\b",
                text
            )
            for word in creation_words
        ):
            return "create"

        # -----------------------------------------------------
        # Research
        # -----------------------------------------------------

        research_words = [
            "research",
            "investigate",
            "analyze",
            "compare"
        ]

        if any(
            re.search(
                rf"\b{re.escape(word)}\b",
                text
            )
            for word in research_words
        ):
            return "research"

        return "answer"

    # =========================================================
    # ARTIFACT DETECTION
    # =========================================================

    def detect_artifact(self, text):

        artifacts = {

            "website": [
                "website",
                "web page",
                "webpage",
                "html",
                "css",
                "frontend",
                "landing page",
                "navbar",
                "login page"
            ],

            "application": [
                "app",
                "application",
                "software",
                "tool"
            ],

            "code": [
                "code",
                "script",
                "program",
                "function",
                "class"
            ],

            "presentation": [
                "ppt",
                "pptx",
                "powerpoint",
                "presentation",
                "slides"
            ],

            "document": [
                "document",
                "pdf",
                "report",
                "word file"
            ]
        }

        # -----------------------------------------------------
        # More specific artifact types must win.
        # -----------------------------------------------------

        priority = [
            "website",
            "presentation",
            "document",
            "application",
            "code"
        ]

        for artifact in priority:

            keywords = artifacts[artifact]

            if any(
                keyword in text
                for keyword in keywords
            ):
                return artifact

        return None

    # =========================================================
    # REFERENCE RESOLUTION
    # =========================================================

    def resolve_reference(
        self,
        original,
        text,
        history,
        explicit_artifact=None
    ):

        reference_words = [
            "this",
            "that",
            "it",
            "same",
            "previous",
            "above",
            "earlier",
            "current",
            "existing"
        ]

        has_reference = any(
            re.search(
                rf"\b{re.escape(word)}\b",
                text
            )
            for word in reference_words
        )

        # -----------------------------------------------------
        # No reference in current request.
        # -----------------------------------------------------

        if not has_reference:
            return {
                "present": False,
                "resolved": None,
                "source": None
            }

        # -----------------------------------------------------
        # CURRENT REQUEST ALWAYS WINS.
        #
        # Example:
        # "Vibecode this website."
        #
        # Even if previous context was "code",
        # "website" is the explicit current artifact.
        # -----------------------------------------------------

        if explicit_artifact:

            return {
                "present": True,
                "resolved": explicit_artifact,
                "source": "current_request"
            }

        # -----------------------------------------------------
        # Existing internal state
        # -----------------------------------------------------

        if self.last_artifact:

            return {
                "present": True,
                "resolved": self.last_artifact,
                "source": "context_state"
            }

        # -----------------------------------------------------
        # Conversation history
        # -----------------------------------------------------

        for message in reversed(history):

            if not isinstance(message, dict):
                continue

            content = str(
                message.get(
                    "content",
                    ""
                )
            ).lower()

            artifact = self.detect_artifact(
                content
            )

            if artifact:

                return {
                    "present": True,
                    "resolved": artifact,
                    "source": "conversation_history"
                }

        # -----------------------------------------------------
        # Unresolved reference
        # -----------------------------------------------------

        return {
            "present": True,
            "resolved": None,
            "source": "unresolved"
        }

    # =========================================================
    # TASK TYPE
    # =========================================================

    def determine_task_type(
        self,
        intent,
        action,
        artifact
    ):

        if intent == "capability_question":
            return "capability"

        if intent == "explanation":
            return "explanation"

        if intent == "software_task":

            if action == "modify":
                return "software_modification"

            if action == "create":
                return "software_creation"

            return "software_question"

        if intent == "modification":

            if artifact:
                return "artifact_modification"

            return "modification"

        if intent == "research":
            return "research"

        return "question_answering"

    # =========================================================
    # CONFIDENCE
    # =========================================================

    def calculate_confidence(
        self,
        text,
        intent,
        domain,
        action,
        artifact
    ):

        score = 0.45

        if intent != "general":
            score += 0.15

        if domain != "general":
            score += 0.10

        if action != "answer":
            score += 0.10

        if artifact:
            score += 0.05

        if text.endswith("?"):
            score += 0.05

        if len(text.split()) >= 3:
            score += 0.05

        return min(
            score,
            0.95
        )

    # =========================================================
    # UNDERSTANDING
    # =========================================================

    def build_understanding(
        self,
        text,
        intent,
        task_type,
        domain,
        action,
        artifact,
        reference
    ):

        parts = [

            f"intent={intent}",

            f"task={task_type}",

            f"domain={domain}",

            f"action={action}"
        ]

        if artifact:

            parts.append(
                f"artifact={artifact}"
            )

        if reference.get("present"):

            resolved = reference.get(
                "resolved"
            )

            if resolved:

                parts.append(
                    f"reference={resolved}"
                )

            else:

                parts.append(
                    "reference=unresolved"
                )

        return ", ".join(parts)

    # =========================================================
    # STATE UPDATE
    # =========================================================

    def update_state(self, contract):

        self.last_task = contract

        artifact = contract.get(
            "artifact"
        )

        if artifact:
            self.last_artifact = artifact

        self.last_topic = contract.get(
            "domain"
        )


# =============================================================
# SINGLETON
# =============================================================

_context_engine = ContextEngine()


def analyze_context(
    user_input,
    conversation_history=None
):

    return _context_engine.analyze(
        user_input,
        conversation_history
    )


# =============================================================
# TERMINAL TEST
# =============================================================

if __name__ == "__main__":

    engine = ContextEngine()

    tests = [

        "Can you vibecode?",

        "What is vibecoding?",

        "Vibecode this website.",

        "Add Create Account to the same HTML.",

        "Make the navbar better.",

        "What is an operating system?",

        "Can you build an AI tool for me?"
    ]

    print()
    print("=" * 70)
    print("ULTRON CONTEXT ENGINE")
    print("=" * 70)

    for test in tests:

        result = engine.analyze(
            test
        )

        print()
        print(
            "USER:",
            test
        )

        print(
            "UNDERSTANDING:",
            result["understanding"]
        )

        print(
            "CONFIDENCE:",
            result["confidence"]
        )