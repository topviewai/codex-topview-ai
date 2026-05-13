def should_skip(step, resume_from, steps):
    """如果 resume_from 指定了某个步骤，跳过该步骤之前的所有阶段。"""
    if not resume_from:
        return False
    if resume_from not in steps:
        return False
    return steps.index(step) < steps.index(resume_from)
