from typing import Dict, List, Literal

from pydantic import BaseModel, Field

# === Rich Text Elements ===


class TextNode(BaseModel):
    nodeType: Literal["text"]
    value: str = Field(..., description="The actual text content.")
    marks: List = Field(default_factory=list)
    data: Dict = Field(default_factory=dict)


class Hyperlink(BaseModel):
    nodeType: Literal["hyperlink"]
    data: Dict[str, str] = Field(
        ..., description="Should contain 'uri' with the destination link."
    )
    content: List[TextNode] = Field(
        ..., description="The clickable text for the hyperlink."
    )


class Paragraph(BaseModel):
    nodeType: Literal["paragraph"]
    data: Dict = Field(default_factory=dict)
    content: List[Hyperlink | TextNode]


class Document(BaseModel):
    nodeType: Literal["document"]
    data: Dict = Field(default_factory=dict)
    content: List[Paragraph]


# === Fixed Content Type Structure ===


class ContentTypeSys(BaseModel):
    type: Literal["Link"]
    linkType: Literal["ContentType"]
    id: Literal["cafeReview"]


class ContentType(BaseModel):
    sys: ContentTypeSys


class EntrySys(BaseModel):
    contentType: ContentType = Field(
        ..., description="Links to the Contentful 'cafeReview' content type."
    )


# === Linked City Entry ===


class EntryLinkSys(BaseModel):
    type: Literal["Link"]
    linkType: Literal["Entry"]
    id: str = Field(
        ...,
        description="Contentful entry ID of the city. This is mapped in the city_mapping.json file.",
    )


class EntryLink(BaseModel):
    sys: EntryLinkSys


# === Latitude/Longitude ===


class LatLon(BaseModel):
    lat: float = Field(..., description="Latitude of the cafe.")
    lon: float = Field(..., description="Longitude of the cafe.")


# === Fields Section ===


class Fields(BaseModel):
    cafeName: Dict[str, str] = Field(..., description="Name of the cafe.")
    authorName: Dict[str, str] = Field(
        ..., description="This should always be Chris Jordan."
    )
    publishDate: Dict[str, str] = Field(
        ..., description="Localized publish date in YYYY-MM-DD format."
    )
    slug: Dict[str, str] = Field(
        ...,
        description="Slug for the url. This should be formatted in lowercase with hyphens between words. It should be the name of the coffee shop, followed by the street name. Example: If the cafe is named Best Coffee and the address is 123 Main St, the slug should be best-coffee-main.",
    )
    excerpt: Dict[str, str] = Field(
        ...,
        description="One-sentence summary of the cafe that provides a simple overview of the cafe.",
    )

    instagramLink: Dict[str, Document] = Field(
        ..., description="The URL for the Instagram account of the cafe."
    )
    facebookLink: Dict[str, Document] = Field(
        ..., description="The URL for the Facebook account of the cafe.."
    )

    overallScore: Dict[str, float] = Field(
        ...,
        description="Overall score from 1–10. This is the average of the coffeeScore, atmosphereScore, serviceScore and foodScore. It should only be to the 1 decimal place. The distribution of scores should roughly follow a bell curve centered around 7.5, with fewer cafes receiving extreme scores (5-7 or 9-10).",
    )
    coffeeScore: Dict[str, float] = Field(
        ...,
        description="Score from 1–10 for coffee quality. Distribution guidelines: 1-3: Poor (major issues, undrinkable), 4-5: Below average (noticeable flaws), 6: Average (acceptable but unremarkable), 7: Good (solid execution), 8: Very good (minor flaws only), 9: Excellent (exceptional quality), 10: Perfect (world-class, rare). Consider factors: bean quality, roast profile, extraction, consistency, temperature, and presentation.",
    )
    atmosphereScore: Dict[str, float] = Field(
        ...,
        description="Score from 1–10 for cafe atmosphere. Distribution guidelines: 1-3: Poor (uncomfortable, major issues), 4-5: Below average (functional but uninspiring), 6: Average (comfortable but generic), 7: Good (pleasant environment), 8: Very good (thoughtful design), 9: Excellent (exceptional ambiance), 10: Perfect (unique, memorable space). Consider: lighting, music, seating comfort, layout, cleanliness, and design cohesion.",
    )
    serviceScore: Dict[str, float] = Field(
        ...,
        description="Score from 1–10 for service quality. Distribution guidelines: 1-3: Poor (rude, major issues), 4-5: Below average (inattentive, slow), 6: Average (functional but impersonal), 7: Good (friendly, efficient), 8: Very good (knowledgeable, attentive), 9: Excellent (exceptional hospitality), 10: Perfect (outstanding, memorable service). Consider: staff knowledge, attitude, efficiency, and handling of busy periods.",
    )
    vibeScore: Dict[str, int] = Field(
        ...,
        description="Score from 1–10 for cafe vibe/coolness factor. Distribution guidelines: 1-3: Generic/chain-like, 4-5: Basic neighborhood cafe, 6: Solid local spot, 7: Hip/trendy place, 8: Local cultural hub, 9: Destination-worthy uniqueness, 10: Iconic/influential in cafe culture. Consider: uniqueness, cultural impact, community role, and overall coolness. Scores of 9-10 should be given to places that are truly exceptional and memorable.",
    )

    vibeDescription: Dict[str, Document] = Field(
        ...,
        description="Text description of the cafe's vibe and atmosphere. - Write exactly 3 sentences, focus on the spirit and atmosphere of the place, describe it as you would to friends, avoid discussing coffee quality, food, or service details, capture the emotional and social experience, DO NOT overlap with other content categories",
    )
    theStory: Dict[str, Document] = Field(
        ...,
        description="Text description of the cafe's origin and story. Write 3-5 sentences, Focus on the cafe's origins and mission, Highlight notable achievements or milestones, Discuss their broader vision and impact, DO NOT focus on coffee specifics, DO NOT use individual names. Do not start by restating the prompt or the name of the cafe within the first sentence.",
    )
    craftExpertise: Dict[str, Document] = Field(
        ...,
        description="Text about the coffee craft and preparation.Write up to 5 sentences, Detail their coffee quality and preparation, Describe barista expertise and service, Highlight special or unique drinks, Discuss seating arrangements and drinkware, Focus on the complete food and drink experience.  Do not start by restating the prompt or the name of the cafe within the first sentence.",
    )
    setsApart: Dict[str, Document] = Field(
        ...,
        description="Text describing what sets the cafe apart.Write 3-4 sentences, Highlight unique differentiators from other cafes, Discuss any special perspective on coffee or design, Focus on standout features or approaches, Emphasize what makes them memorable.  Do not start by restating the prompt or the name of the cafe within the first sentence.",
    )

    cafeAddress: Dict[str, str] = Field(
        ..., description="Full street address of the cafe."
    )
    cityReference: Dict[str, EntryLink] = Field(
        ...,
        description="Reference to the linked city entry in Contentful. This will be the ID of the city that the cafe is located in.",
    )
    cafeLatLon: Dict[str, LatLon] = Field(
        ..., description="Latitude and longitude coordinates of the cafe."
    )
    placeId: Dict[str, str] = Field(..., description="Google Place ID.")


# === Full Entry Object ===


class Entry(BaseModel):
    sys: EntrySys = Field(
        ..., description="System content type reference for Contentful."
    )
    fields: Fields = Field(
        ..., description="Localized field values for the cafe review."
    )


# === Upload Payload ===


class ContentfulCafeReviewPayload(BaseModel):
    entries: List[Entry] = Field(
        ..., description="List of cafe review entries for upload to Contentful."
    )
