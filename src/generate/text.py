"""Free-text assembly from phrase banks.

No LLM is used. Each text dataset is built by drawing an opening, one or two
reason phrases, a specific detail and a closing from the banks below, then
substituting names, sites and shifts.
"""

from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# Exit interview reason banks. The bank a phrase is drawn from is the ground
# truth reason; the pipeline never sees that label, only the assembled text.
# ---------------------------------------------------------------------------

EXIT_REASON_BANKS = {
    "schedule_workload": [
        "my schedule changed and the new shifts are impossible to manage",
        "the rotating schedule after the center reorganisation does not work for me",
        "I am working late evenings every week since the shift change",
        "the weekend and evening rotations are unsustainable with my family",
        "my shift was moved to close and I cannot arrange childcare",
        "the schedule is set with very little notice and changes week to week",
        "call volumes mean I am on the phones back to back with no time between calls",
        "the workload went up sharply after the team was restructured",
        "I am handling far more calls per shift than the role is scoped for",
        "the new shift pattern removed the flexibility I was promised",
        "breaks are routinely cut short because of queue pressure",
        "the split shifts mean I am effectively here all day",
        "after the schedule change my commute doubled and there is no relief",
        "the workload is more than one person can carry at this queue depth",
        "we were told the shift change was temporary but it has been months",
        "I cannot keep covering open shifts that nobody else will take",
        "the mandatory overtime on top of the new schedule leaves no recovery time",
        "the staffing model changed and my team is now covering two queues",
    ],
    "compensation": [
        "the pay is not competitive for the work I am doing",
        "I received an offer elsewhere with a materially higher base",
        "my pay has not kept up with the market over the last two years",
        "I am paid below what the role is advertised at externally",
        "the bonus did not reflect the results my team delivered",
        "the incentive plan was changed and my earnings dropped",
        "I am carrying more responsibility without a pay adjustment",
        "the pay band for my role is below comparable positions elsewhere",
        "my last increase was smaller than the cost of living change",
        "I was told a pay review would happen and it never did",
        "the salary for this level is not enough to retain people in this market",
        "the commission structure makes the target unrealistic",
        "I am doing a higher-level role at the lower-level pay",
        "the total package does not compare with what I have been offered",
        "pay equity on my team is unclear and I cannot get a straight answer",
    ],
    "career_growth": [
        "there is no path for promotion in my role",
        "I have been at the same level for years with no advancement",
        "I was passed over for a promotion that I had been told I was ready for",
        "development conversations never turn into a plan or an opening",
        "I want to grow into analytics and data work but there is no route here",
        "the work has become repetitive and I am not learning new skills",
        "I asked for stretch assignments and none came",
        "my manager could not tell me what the next role for me would be",
        "there is no rotation or internal mobility I can access from this team",
        "I am ready for more scope but the team has no openings above me",
        "the succession plan does not include anyone at my level",
        "I want to specialise and the only way to do that is elsewhere",
        "training is available but it does not lead anywhere in this organisation",
        "I have outgrown the role and there is nowhere to move internally",
        "the promotion process is opaque and depends on who you know",
    ],
    "manager_relationship": [
        "my relationship with my manager has broken down",
        "my manager does not give me feedback until something goes wrong",
        "I do not get the support I need from my manager on escalations",
        "my manager takes credit for the team's work",
        "decisions change constantly and my manager will not commit to anything",
        "I raised concerns with my manager repeatedly and nothing changed",
        "my manager is not fair about how shifts and tasks are distributed",
        "there is a lot of favouritism and it affects who gets opportunities",
        "I do not feel I can raise a problem without it being held against me",
        "my manager micromanages and it makes the work harder than it needs to be",
        "I have had three managers in a year and no consistent direction",
        "my manager is not present and the team is left to sort things out",
        "performance feedback is inconsistent across my team",
        "I was promised a conversation about my concerns and it never happened",
        "the management style on this team does not work for me",
    ],
    "relocation_personal": [
        "I am relocating and cannot continue in this office",
        "my family is moving out of state",
        "I am moving closer to my parents and cannot commute here",
        "I am returning to study and need to reduce my hours",
        "a family member needs care and I need to be closer to them",
        "I am moving abroad for personal reasons",
        "my partner's job is relocating the household",
        "I need a role that fits around a health situation in the family",
        "I am taking time away to support my family",
        "the commute became unmanageable after I moved house",
        "personal circumstances mean the onsite schedule no longer works",
        "I am stepping back from full-time work for a period",
        "I am moving to be closer to family and cannot make the commute",
        "my visa situation means I need to change employers",
        "I need to reduce my hours while I care for a relative",
    ],
    "health_burnout": [
        "I am exhausted and I have not been able to recover",
        "I am burned out and it is affecting my health",
        "I am running on fumes at the end of every week",
        "the pace on this team is not sustainable and I need to step away",
        "I have not taken a proper break in months",
        "the workload is affecting my sleep and my health",
        "I am taking this step because I need to look after my wellbeing",
        "the stress of the queue has become too much to carry",
        "I have been unwell and the workload has not been adjusted",
        "I am no longer able to keep up with the pace without it costing me",
        "my doctor advised me to reduce my workload",
        "the constant pressure has worn me down over the last year",
        "there are no breaks and no time to recover between shifts",
        "I am exhausted every day and the schedule gives me no recovery",
        "the constant pressure has left me with no energy outside work",
    ],
    "other": [
        "the role turned out to be different from what I was told",
        "I am moving to a different industry",
        "I have decided to take a break from work",
        "I am joining a smaller company where I can have more influence",
        "I was offered a role closer to home",
        "the work is not what I want to do long term",
        "I have an opportunity that I cannot pass up",
        "I am leaving for a role with a different working model",
        "I have been offered a role that fits my long-term plans better",
        "the team is being reorganised and my role no longer exists",
        "I am returning to study full time",
        "I want to work in a smaller team with a broader scope",
        "the contract came to an end and I have accepted another role",
        "I am taking a role that lets me work closer to my community",
        "I have decided to start my own business",
        "the timing is right to try something different",
    ],
}

# Schedule and workload language that does not assume a phone queue. Exit
# interviews outside contact centres draw from this bank.
EXIT_REASON_BANKS_GENERIC = {
    "schedule_workload": [
        "my schedule changed and the new pattern does not work for me",
        "the rotating schedule after the reorganisation is impossible to plan around",
        "I am working late every week since the shift change",
        "the weekend and evening rotations are unsustainable with my family",
        "my shift was moved and I cannot arrange childcare",
        "the schedule is set with very little notice and changes week to week",
        "the workload went up sharply after the team was restructured",
        "I am carrying more work than the role is scoped for",
        "the new shift pattern removed the flexibility I was promised",
        "breaks are routinely cut short because of delivery pressure",
        "the split shifts mean I am effectively here all day",
        "after the schedule change my commute doubled and there is no relief",
        "the workload is more than one person can carry",
        "we were told the shift change was temporary but it has been months",
        "the mandatory overtime on top of the new schedule leaves no recovery time",
        "staffing changed and my team is now covering two workstreams",
    ],
}

EXIT_OPENERS = [
    "I have appreciated the time here but",
    "After a lot of thought,",
    "I want to be straight with you,",
    "To be honest,",
    "I have enjoyed my team but",
    "It has been a difficult decision,",
    "Looking back over the last year,",
    "I want to give you the real reasons,",
]

EXIT_CLOSERS = [
    "Thank you for the opportunities.",
    "I wish the team well.",
    "I hope this is useful feedback.",
    "I have no complaints about my colleagues.",
    "I would happily recommend the team to others.",
    "I hope things improve for the people still here.",
    "Nothing personal against the team.",
    "I hope this can be acted on.",
]

EXIT_DETAILS = {
    "contact_center": [
        "The {shift} {site} shift is the specific problem.",
        "It is worst on the {shift} shift at {site}.",
        "The change at {site} affected the whole {shift} rotation.",
        "On the {shift} shift we are the last to get any relief.",
    ],
    "generic": [
        "This has been building since {year}.",
        "It became clear over the last {months} months.",
        "I raised it in my last review and nothing changed.",
        "It has been the case for most of this year.",
    ],
}

SHIFTS = ["evening", "early", "late", "weekend", "overnight"]

# ---------------------------------------------------------------------------
# Engagement survey comments
# ---------------------------------------------------------------------------

SURVEY_COMMENTS = {
    "manager_positive": [
        "My manager is clear about priorities and backs the team up.",
        "I get useful feedback from my manager every week.",
        "My manager makes time for me and knows what I am working on.",
        "The team is well run and I know what is expected of me.",
        "My manager recognises good work in public and in private.",
        "My manager trusts me to get on with the work and steps in when needed.",
        "I always know where I stand with my manager and what to focus on.",
        "My manager removes blockers quickly instead of leaving them to the team.",
        "The weekly one-to-one is genuinely useful and never cancelled.",
        "My manager is approachable and gives me room to try things.",
        "Feedback here is specific and helps me improve rather than just score me.",
        "My manager defends the team's time when other groups pile on work.",
        "Decisions are explained clearly, even the ones I disagree with.",
        "My manager has helped me build a plan for the next role.",
        "The team feels stable because my manager is consistent.",
        "My manager notices when someone is overloaded and rebalances the work.",
        "I can raise a problem without it becoming a formal issue.",
    ],
    "manager_negative": [
        "My manager is not consistent and it makes planning impossible.",
        "I do not get feedback unless something has gone wrong.",
        "The team gets conflicting direction from management.",
        "My manager is stretched too thin to support the team.",
        "Priorities change weekly and nobody explains why.",
        "My manager avoids difficult conversations until the problem is large.",
        "I find out about decisions that affect my work after they are made.",
        "Support on escalations is slow and usually comes with blame.",
        "My manager says yes to every request and the team absorbs the cost.",
        "There is no clear owner for the work, so it keeps landing on me.",
        "My manager rarely shows up to the team meeting and sends notes instead.",
        "Feedback is vague and changes depending on who else is in the room.",
        "I have had three managers this year and each one started over.",
        "My manager protects their own position more than the team.",
        "Work is assigned unevenly and nobody explains the reasoning.",
    ],
    "workload_negative": [
        "The queue is unmanageable and there is no slack in the schedule.",
        "I am covering two roles and cannot do either properly.",
        "There is no time between calls and no time to think.",
        "The shift pattern leaves no time to recover.",
        "We are permanently short-staffed and it is wearing people down.",
        "I skip breaks most days because the volume never lets up.",
        "The team is carrying a vacancy and the work was never reduced.",
        "Every week adds another report while nothing is taken away.",
        "I am doing the work of two people and the queue still grows.",
        "There is no quiet period to catch up on anything.",
        "I finish the day with a backlog I know I cannot clear.",
        "The handover between shifts is too short for the volume we handle.",
        "Time off is covered by the same small group every time.",
        "The workload spikes are treated as normal rather than temporary.",
        "I cannot take leave without coming back to a mountain of work.",
    ],
    "schedule_negative": [
        "The new schedule is the main problem for me.",
        "Shift changes are given with almost no notice.",
        "The rotating shifts make it impossible to plan anything.",
        "The weekend rota is unfair and falls on the same people.",
        "I cannot plan childcare around the current schedule.",
        "The latest rota changed my start time with two days notice.",
        "Split shifts make the day feel twice as long as it is.",
        "I was promised a fixed shift and it has changed twice since.",
        "The evening rotation has no predictable end time.",
        "My days off move every month and I cannot book anything.",
        "The schedule is published too late to arrange transport.",
        "Weekend coverage is assigned by seniority and I always get it.",
        "The new shift pattern added a long commute on both ends.",
        "Nobody asks before moving people between shifts.",
        "The rota is rebuilt every week and the same people lose out.",
    ],
    "burnout": [
        "I am exhausted and there are no breaks in the day.",
        "The pace here is unsustainable and I am burned out.",
        "I am running on empty most weeks.",
        "I have not had a proper break in months.",
        "I am burned out and it is affecting my home life.",
        "The workload is not sustainable over a full year.",
        "I am worn down by the constant queue pressure.",
        "I have started dreading the start of every shift.",
        "The pace has taken a toll on my sleep and my health.",
        "There is no recovery time between the busy periods any more.",
        "I am exhausted by the middle of the week and it never resets.",
        "The stress is following me home and I cannot switch off.",
        "I have raised the workload twice and nothing has changed.",
        "Every day feels like a sprint and there is no end in sight.",
        "I am close to the point where I cannot keep going at this pace.",
    ],
    "growth_negative": [
        "I do not see a path to promotion from my role.",
        "I am not learning anything new in this role.",
        "Development conversations do not lead to anything.",
        "I would like to move into data work but there is no route.",
        "My skills are not being used and there is nowhere to grow.",
        "I have asked for stretch work and never received any.",
        "The promotion process is unclear and nobody can explain it.",
        "My last development plan was never reviewed again.",
        "There are no openings above me and no plan for when there are.",
        "I am doing the same work I did two years ago.",
        "Training is offered but it does not connect to a role change.",
        "I would need to leave the team to learn anything new.",
        "Internal moves are blocked by my current manager.",
        "I have outgrown the scope of this role.",
        "Nobody has talked to me about what comes next.",
    ],
    "pay_negative": [
        "The pay does not reflect the level of the work.",
        "I am paid below the market for what I do.",
        "The bonus did not match the results the team delivered.",
        "Pay has not kept up with the cost of living.",
        "My pay has not moved while the scope of the role has grown.",
        "New hires seem to join on more than people already doing the job.",
        "The incentive plan changed and my earnings went down.",
        "I am carrying a higher-level workload at the lower band.",
        "Pay decisions are opaque and never explained.",
        "The increase this year was smaller than inflation.",
        "The total package is not competitive for this market.",
        "I would need a promotion to get a meaningful raise.",
        "Pay equity on the team is unclear and nobody will discuss it.",
        "The commission target is not achievable with the current volume.",
        "My salary has been at the same point in the band for years.",
    ],
    "positive": [
        "The team is strong and I enjoy the work.",
        "Good colleagues and a clear purpose.",
        "I am proud of what the team delivers.",
        "The flexibility here works well for me.",
        "I would recommend this team to a friend.",
        "The work is varied and I get to solve real problems.",
        "I like the people I work with and we help each other.",
        "The team has a clear goal and we are trusted to reach it.",
        "I have learned a lot this year and the work keeps me interested.",
        "The hybrid pattern gives me the balance I need.",
        "I feel my contribution is visible and valued.",
        "The tools are good enough to do the job properly.",
        "I can make decisions in my area without layers of approval.",
        "The team handles pressure well and looks after each other.",
        "This is the best team I have worked on.",
    ],
}

BURNOUT_MARKERS = [
    "exhausted",
    "burned out",
    "burnout",
    "no breaks",
    "unsustainable",
    "running on empty",
    "running on fumes",
    "worn down",
    "not sustainable",
]

# ---------------------------------------------------------------------------
# Manager review comments
# ---------------------------------------------------------------------------

MANAGER_COMMENT_SKILLS = [
    "strong SQL and data modelling skills",
    "solid Python skills and good instincts for experimentation",
    "excellent process mapping and documentation",
    "a reliable eye for data quality",
    "strong Excel automation and reporting skills",
    "good machine learning fundamentals",
    "a natural at pipeline design and tooling",
    "strong analytical writing and stakeholder framing",
]

MANAGER_COMMENTS = {
    "high": [
        "{name} is one of the strongest people on the team this year, with {skill}.",
        "{name} delivered consistently and shows {skill}.",
        "Outstanding year for {name}, who brings {skill}.",
        "{name} exceeded expectations and demonstrates {skill}.",
        "{name} sets the standard on the team, particularly with {skill}.",
    ],
    "mid": [
        "{name} met expectations and is developing {skill}.",
        "Steady year for {name}; {skill} is coming along well.",
        "{name} is dependable and is building {skill}.",
        "{name} delivered what was asked and is improving {skill}.",
        "Solid year for {name}, with growth in {skill}.",
    ],
    "low": [
        "{name} has not consistently met expectations this year.",
        "{name} needs to improve the quality and pace of delivery.",
        "{name} requires closer direction and more attention to detail.",
        "{name} is a work in progress against the role expectations.",
        "Mixed year for {name}; results were uneven.",
    ],
}

# Comments that do not name a skill. Only the P2 and P6 cohorts get skill
# language, so a skills search points at those people instead of naming the
# same tools for the whole operations population.
MANAGER_COMMENT_GENERIC = {
    "high": [
        "{name} is one of the strongest people on the team this year.",
        "{name} delivered consistently across the year.",
        "Outstanding year for {name}, including work beyond the role.",
        "{name} exceeded expectations and set the pace for the team.",
        "{name} sets the standard on the team.",
    ],
    "mid": [
        "{name} met expectations and delivered reliably.",
        "Steady year for {name}, with progress on the development plan.",
        "{name} is dependable and works well with the team.",
        "{name} delivered what was asked and grew into the role.",
        "Solid year for {name}, with a consistent contribution.",
    ],
    "low": MANAGER_COMMENTS["low"],
}

# ---------------------------------------------------------------------------
# Job descriptions
# ---------------------------------------------------------------------------

ROUTINE_TASK_BANK = [
    "process incoming documents and key the relevant fields into the core system",
    "review queues and clear routine exceptions against a documented checklist",
    "reconcile daily transaction reports and escalate mismatches",
    "handle inbound requests and route them to the correct workflow",
    "complete standard data entry and quality checks on customer records",
    "follow the written procedure to complete repetitive processing steps",
    "maintain case notes and update the tracking spreadsheet",
    "validate forms against the checklist and return incomplete items",
]

CONSULTATIVE_TASK_BANK = [
    "partner with business stakeholders to define requirements and measures",
    "design, build and maintain pipelines and reporting for the function",
    "lead analysis that informs decisions and improves outcomes",
    "coach colleagues and set direction for the wider team",
    "own the roadmap for the function and report progress to leadership",
]

SKILL_BANK = [
    "SQL", "process mapping", "data quality", "Excel automation",
    "Python", "dashboarding", "stakeholder management", "experimentation",
]


def _draw(rng: np.random.Generator, bank) -> str:
    return bank[int(rng.integers(0, len(bank)))]


def exit_comment(
    rng: np.random.Generator,
    reasons,
    *,
    contact_center: bool,
    site: str,
    year: int,
    months: int,
    burnout: bool,
) -> str:
    """Assemble an exit interview comment from one or two ground-truth reasons."""
    opener = _draw(rng, EXIT_OPENERS)
    parts = []
    for reason in reasons:
        if reason in EXIT_REASON_BANKS:
            bank = EXIT_REASON_BANKS[reason]
            if reason == "schedule_workload" and not contact_center:
                bank = EXIT_REASON_BANKS_GENERIC[reason]
            parts.append(_draw(rng, bank))
    body = parts[0]
    if len(parts) > 1:
        body = f"{parts[0]}, and {parts[1]}"

    detail_bank = EXIT_DETAILS["contact_center"] if contact_center else EXIT_DETAILS["generic"]
    detail = _draw(rng, detail_bank).format(
        shift=_draw(rng, SHIFTS), site=site, year=year, months=months
    )
    closer = _draw(rng, EXIT_CLOSERS)
    text = f"{opener} {body}. {detail} {closer}"
    if burnout and "burnout" not in text.lower() and "exhaust" not in text.lower():
        text = f"{text} I am exhausted and the schedule gives me no recovery."
    return text


def survey_comment(rng: np.random.Generator, keys) -> str:
    key = keys[int(rng.integers(0, len(keys)))]
    return _draw(rng, SURVEY_COMMENTS[key])


def manager_comment(rng: np.random.Generator, name: str, band: str, skill: str | None = None) -> str:
    if skill is None:
        out = _draw(rng, MANAGER_COMMENT_GENERIC[band]).format(name=name)
    else:
        template = _draw(rng, MANAGER_COMMENTS[band])
        out = template.format(name=name, skill=skill)
    return out[:1].upper() + out[1:]


def job_description(
    rng: np.random.Generator,
    title: str,
    *,
    routine: bool,
    skills=None,
    consultative: bool = False,
) -> str:
    if routine:
        tasks = []
        while len(tasks) < 4:
            t = _draw(rng, ROUTINE_TASK_BANK)
            if t not in tasks:
                tasks.append(t)
    else:
        tasks = []
        while len(tasks) < 3:
            t = _draw(rng, CONSULTATIVE_TASK_BANK)
            if t not in tasks:
                tasks.append(t)
    bullets = "; ".join(tasks)
    text = f"The {title} is responsible to {bullets}."
    if skills:
        text += " Required skills include " + ", ".join(skills) + "."
    if consultative:
        text += " The role partners closely with the wider function."
    return text
