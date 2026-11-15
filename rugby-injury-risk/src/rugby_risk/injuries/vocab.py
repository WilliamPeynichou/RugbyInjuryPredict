"""Injury vocabularies (F15). Single code definition; a unit test checks docs/04 concordance."""

from enum import StrEnum


class BodyRegion(StrEnum):
    HEAD = "head"
    NECK = "neck"
    SHOULDER = "shoulder"
    ARM = "arm"
    TRUNK = "trunk"
    HIP_GROIN = "hip_groin"
    THIGH = "thigh"
    KNEE = "knee"
    LOWER_LEG = "lower_leg"
    ANKLE = "ankle"
    FOOT = "foot"
    OTHER = "other"


class InjuryType(StrEnum):
    CONCUSSION = "concussion"
    LIGAMENT = "ligament"
    MUSCLE = "muscle"
    FRACTURE = "fracture"
    CONTUSION = "contusion"
    TENDON = "tendon"
    OTHER = "other"
    UNKNOWN = "unknown"


class OnsetContext(StrEnum):
    MATCH = "match"
    TRAINING = "training"
    UNKNOWN = "unknown"
