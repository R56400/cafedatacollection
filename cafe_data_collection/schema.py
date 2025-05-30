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
        description="Score from 1–10 for coffee quality. Base ranges: 6.0-6.9: Decent specialty coffee but inconsistent, 7.0-8.2: Solid specialty cafe doing everything right, 8.3-9.7: Exceptional quality with unique offerings or perfect execution, 9.8-10: Among the absolute best in the city. IMPORTANT SCORING TRIGGERS: Start at 8.7+ if: cafe is consistently mentioned in 'best coffee in city' lists, has won regional/national awards, or is known for unique/innovative coffee programs. Add 0.3-0.5 points when: multiple independent sources praise coffee quality, cafe is considered a coffee destination, or roasts their own exceptional beans.",
    )
    atmosphereScore: Dict[str, float] = Field(
        ...,
        description="Score from 1–10 for cafe atmosphere. Base ranges: 6.0-6.9: Basic but functional cafe space, 7.0-8.2: Well-designed with good ambiance, 8.3-9.7: Exceptional design that enhances the experience, 9.8-10: Iconic spaces that are unmatched in the city. IMPORTANT SCORING TRIGGERS: Start at 8.7+ if: space is frequently featured in design magazines, considered a landmark/destination for its design, or sets new trends in cafe design. Add 0.3-0.5 points when: multiple reviews specifically praise the space design, cafe has unique architectural elements, or creates an exceptional atmosphere that defines the neighborhood.",
    )
    serviceScore: Dict[str, float] = Field(
        ...,
        description="Score from 1–10 for service quality. Base ranges: 6.0-6.9: Professional but room for improvement, 7.0-7.9: Consistently good service with knowledgeable staff, 8.0-9.5: Outstanding service that elevates the experience, 9.6-10: Sets the standard for cafe service in the city. IMPORTANT SCORING TRIGGERS: Start at 8.7+ if: service is consistently praised across reviews, staff demonstrates exceptional coffee knowledge, or service enhances the overall experience notably. Add 0.3-0.5 points when: multiple reviews mention standout service experiences, staff goes above and beyond consistently, or service creates memorable experiences.",
    )
    vibeScore: Dict[str, int] = Field(
        ...,
        description="Score from 1–10 for cafe vibe/coolness factor. Note: This is NOT included in the overall score. Base ranges: 6.0-6.9: Pleasant but unremarkable, 7.0-8.2: Notable spot with character, 8.3-9.2: Influential place that draws people in, 9.3-10: Defines coffee culture for the city. IMPORTANT SCORING TRIGGERS: Start at 8.7+ if: cafe is considered a cultural institution, sets trends for the city's coffee scene, or is a must-visit destination. Add 0.3-0.5 points when: cafe has significant cultural impact, creates unique community experiences, or is consistently mentioned as a city highlight.",
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
