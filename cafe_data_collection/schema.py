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
        description="Overall score from 1–10. This is the average of the coffeeScore, atmosphereScore, and serviceScore (not including vibeScore). It should only be to the 1 decimal place. Since we're selecting notable cafes, expect most scores between 7.0-9.7, but use the full range to differentiate cafes.",
    )
    coffeeScore: Dict[str, float] = Field(
        ...,
        description="Score from 1–10 for coffee quality. Consider: 6.0-6.9: Decent specialty coffee but inconsistent, 7.0-8.2: Solid specialty cafe doing everything right, 8.3-9.7: Exceptional quality with unique offerings or perfect execution, 9.8-10: Among the absolute best in the city. Use the full range of the score, and don't just bias to round numbers. If a cafe is consitntly mentioned at a top spot, add 0.3-0.5 points.",
    )
    atmosphereScore: Dict[str, float] = Field(
        ...,
        description="6.0-6.9: Basic functional. 7.0-8.2: Great atmosphere. 8.3-9.7: Exceptional atmosphere. 9.8-10: Iconic space. Add 0.3-0.5 for: widespread praise/unique architecture/neighborhood icon.",
    )
    serviceScore: Dict[str, float] = Field(
        ...,
        description="6.0-6.9: Professional basic. 7.0-7.9: Consistently good. 8.0-9.5: Outstanding. 9.6-10: Sets standards. Add 0.3-0.5 for: standout service/staff excellence/memorable experiences.",
    )
    vibeScore: Dict[str, int] = Field(
        ...,
        description="NOT in overall score. Integer from 6-10. 6-7: Pleasant. 8-9: Notable character. 9-10: Culture-defining.",
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
