"""Static vocabularies used to make records realistic. All synthetic."""

FIRST_NAMES = [
    "Aarav", "Aditi", "Ananya", "Arjun", "Diya", "Ishaan", "Kavya", "Meera", "Neha", "Nikhil",
    "Priya", "Rahul", "Riya", "Rohan", "Sanjana", "Siddharth", "Sneha", "Tanvi", "Varun", "Vikram",
    "Yash", "Zara", "Aisha", "Kabir", "Lakshmi", "Manish", "Pooja", "Rakesh", "Swati", "Uday",
    "Olivia", "Liam", "Emma", "Noah", "Ava", "Ethan", "Sophia", "Lucas", "Mia", "Mason",
    "Chloe", "James", "Grace", "Daniel", "Hannah", "Samuel", "Leah", "Owen", "Nora", "Isaac",
    "Fatima", "Omar", "Mei", "Wei", "Hiro", "Yuki", "Carlos", "Lucia", "Mateo", "Sofia",
]
LAST_NAMES = [
    "Sharma", "Verma", "Iyer", "Reddy", "Nair", "Patel", "Gupta", "Rao", "Menon", "Kulkarni",
    "Joshi", "Das", "Bose", "Chopra", "Mehta", "Singh", "Kapoor", "Pillai", "Banerjee", "Shetty",
    "Smith", "Johnson", "Brown", "Taylor", "Wilson", "Clarke", "Walker", "Hughes", "Evans", "Wright",
    "Khan", "Ali", "Chen", "Wang", "Tanaka", "Sato", "Garcia", "Lopez", "Martins", "Silva",
]

DEPT_WEIGHTS = {"Engineering": 0.30, "Sales": 0.18, "Customer Success": 0.12, "Operations": 0.12,
                "Product": 0.08, "Marketing": 0.08, "Finance": 0.06, "HR": 0.06}
LOCATION_WEIGHTS = {"Bengaluru": 0.30, "Hyderabad": 0.20, "Pune": 0.15, "Chennai": 0.10,
                    "Remote-IN": 0.12, "London": 0.07, "Austin": 0.06}

IC_TITLES = {"Engineering": "Software Engineer", "Sales": "Account Executive",
             "Customer Success": "Customer Success Specialist", "Operations": "Operations Analyst",
             "Product": "Product Manager", "Marketing": "Marketing Specialist",
             "Finance": "Financial Analyst", "HR": "HR Generalist"}
LEVEL_PREFIX = {"L1": "Associate ", "L2": "", "L3": "Senior ", "L4": "Lead ", "L5": "Principal "}

GOAL_TITLES = {
    "business": ["Grow {dept} revenue contribution", "Deliver H{h} {dept} roadmap commitments",
                 "Improve {dept} unit economics"],
    "customer": ["Raise customer satisfaction for {dept} touchpoints", "Reduce customer-reported issues",
                 "Improve onboarding experience"],
    "operational": ["Automate recurring {dept} workflows", "Improve process cycle time",
                    "Strengthen {dept} reporting accuracy"],
    "team": ["Mentor and grow team capability", "Improve cross-team collaboration",
             "Raise team engagement score"],
    "development": ["Complete advanced certification", "Build expertise in a new domain",
                    "Lead a knowledge-sharing series"],
}
CATEGORY_WEIGHTS = {"business": 0.34, "customer": 0.2, "operational": 0.22, "team": 0.12, "development": 0.12}

# description, metric_type, unit, direction, (start_lo, start_hi), (delta_lo, delta_hi)
KR_TEMPLATES = {
    "Engineering": [("Ship production features", "count", "features", "increase", (0, 0), (4, 12)),
                    ("Reduce p95 API latency", "duration", "ms", "decrease", (420, 900), (80, 300)),
                    ("Raise automated test coverage", "percentage", "%", "increase", (45, 70), (8, 20)),
                    ("Cut open P1 defects", "count", "defects", "decrease", (18, 40), (8, 15))],
    "Sales": [("Close new ARR", "currency", "USD", "increase", (0, 0), (150000, 900000)),
              ("Build qualified pipeline", "currency", "USD", "increase", (0, 0), (400000, 2500000)),
              ("Win new logos", "count", "logos", "increase", (0, 0), (3, 15))],
    "Customer Success": [("Raise NPS", "count", "points", "increase", (25, 45), (5, 15)),
                         ("Reduce churned accounts", "count", "accounts", "decrease", (20, 45), (5, 15)),
                         ("Increase renewal rate", "percentage", "%", "increase", (78, 88), (3, 8))],
    "Operations": [("Automate manual processes", "count", "processes", "increase", (0, 0), (3, 10)),
                   ("Reduce ticket resolution time", "duration", "hours", "decrease", (30, 60), (8, 20)),
                   ("Improve SLA attainment", "percentage", "%", "increase", (82, 92), (3, 7))],
    "Product": [("Launch roadmap epics", "count", "epics", "increase", (0, 0), (2, 6)),
                ("Increase feature adoption", "percentage", "%", "increase", (20, 40), (8, 20)),
                ("Complete customer discovery interviews", "count", "interviews", "increase", (0, 0), (10, 30))],
    "Marketing": [("Generate marketing qualified leads", "count", "MQLs", "increase", (0, 0), (300, 1500)),
                  ("Reduce cost per lead", "currency", "USD", "decrease", (90, 160), (15, 45)),
                  ("Grow organic traffic", "percentage", "%", "increase", (0, 0), (10, 35))],
    "Finance": [("Shorten month-end close", "duration", "days", "decrease", (8, 12), (2, 4)),
                ("Reduce reconciliation exceptions", "count", "exceptions", "decrease", (40, 90), (15, 40)),
                ("Improve forecast accuracy", "percentage", "%", "increase", (80, 88), (3, 8))],
    "HR": [("Reduce time to hire", "duration", "days", "decrease", (40, 60), (8, 18)),
           ("Raise engagement survey participation", "percentage", "%", "increase", (60, 75), (8, 18)),
           ("Deliver training sessions", "count", "sessions", "increase", (0, 0), (6, 20))],
}
GENERIC_KRS = [("Complete learning hours", "count", "hours", "increase", (0, 0), (12, 40)),
               ("Deliver knowledge-sharing sessions", "count", "sessions", "increase", (0, 0), (2, 6))]

EVIDENCE_BY_DEPT = {"Engineering": ["repository", "ticket", "dashboard"], "Sales": ["crm_record", "dashboard"],
                    "Customer Success": ["crm_record", "dashboard", "ticket"],
                    "Operations": ["ticket", "dashboard", "document"], "Product": ["document", "ticket"],
                    "Marketing": ["dashboard", "document"], "Finance": ["document", "dashboard"],
                    "HR": ["document", "dashboard"]}

CHECKIN_NOTES = {"high": ["On track, momentum is strong.", "Ahead of plan this period.",
                          "Milestones delivered as planned."],
                 "medium": ["Progressing; a few dependencies to unblock.", "Slightly behind, recovery plan in place.",
                            "Steady progress with minor risks."],
                 "low": ["Blocked on cross-team dependency.", "Behind plan; scope under discussion.",
                         "Resourcing gap is slowing delivery."]}
OVERACHIEVE_RATIONALES = ["Large deal closed earlier than forecast.", "Automation delivered extra capacity.",
                          "Scope expanded with manager approval.", "Market tailwind exceeded plan."]
TARGET_CHANGE_RATIONALES = ["Re-baselined after re-org.", "Business priorities shifted mid-cycle.",
                            "Target corrected after data audit.", "Scope reduced due to dependency slip."]
FEEDBACK_COMMENTS = {5: "Consistently role-model behaviour; clear impact beyond the team.",
                     4: "Strong, reliable performance with visible impact.",
                     3: "Meets expectations; solid and dependable.",
                     2: "Inconsistent; needs focused improvement in this area.",
                     1: "Significant gap; requires immediate support."}
MANAGER_SUMMARIES = ["Delivered core commitments; focus next on scaling impact.",
                     "Strong cycle with clear ownership of outcomes.",
                     "Mixed results; development plan agreed.",
                     "Solid contributor; ready for broader scope."]
PLAN_OBJECTIVES = {"COMP-01": "Improve planning and delivery predictability",
                   "COMP-02": "Build stronger cross-team working relationships",
                   "COMP-03": "Deepen understanding of customer needs",
                   "COMP-04": "Close functional / technical skill gaps",
                   "COMP-05": "Communicate status and risks more clearly",
                   "COMP-06": "Develop coaching and delegation skills"}

COMPETENCIES = [
    ("COMP-01", "Delivery & Execution", "core", "Plans and delivers outcomes reliably", "all"),
    ("COMP-02", "Collaboration", "core", "Works effectively across teams", "all"),
    ("COMP-03", "Customer Focus", "core", "Understands and serves customer needs", "all"),
    ("COMP-04", "Functional Expertise", "technical", "Depth of role-specific skill", "all"),
    ("COMP-05", "Communication", "core", "Communicates clearly and openly", "all"),
    ("COMP-06", "People Leadership", "leadership", "Coaches, delegates and grows people", "managers"),
]
