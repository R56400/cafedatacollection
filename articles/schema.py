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
    id: Literal["coffeeArticle"]


class ContentType(BaseModel):
    sys: ContentTypeSys


class EntrySys(BaseModel):
    contentType: ContentType = Field(
        ..., description="Links to the Contentful 'coffeeArticle' content type."
    )


# === Asset Link Structure ===


class AssetLinkSys(BaseModel):
    type: Literal["Link"]
    linkType: Literal["Asset"]
    id: str = Field(..., description="Contentful asset ID.")


class AssetLink(BaseModel):
    sys: AssetLinkSys


# === Fields Section ===


class Fields(BaseModel):
    articleTitle: Dict[str, str] = Field(..., description="Title of the article.")
    articleSlug: Dict[str, str] = Field(
        ...,
        description="URL-friendly version of the title, using hyphens instead of spaces.",
    )
    articlePublishDate: Dict[str, str] = Field(
        ..., description="Publish date in YYYY-MM-DD format."
    )
    authorName: Dict[str, str] = Field(..., description="Name of the article author.")
    articleHeroImage: Dict[str, AssetLink] = Field(
        ..., description="Main image for the article."
    )
    articleExcerpt: Dict[str, str] = Field(
        ..., description="Short summary of the article."
    )
    articleTags: Dict[str, List[str]] = Field(
        default_factory=lambda: {"en-US": []},
        description="List of tags for the article.",
    )
    articleFeatured: Dict[str, bool] = Field(
        default_factory=lambda: {"en-US": False},
        description="Whether the article is featured.",
    )
    articleContent: Dict[str, Document] = Field(
        ..., description="Main content of the article in rich text format."
    )
    articleGallery: Dict[str, List[AssetLink]] = Field(
        default_factory=lambda: {"en-US": []},
        description="List of images for the article gallery.",
    )
    videoEmbed: Dict[str, str] = Field(
        default_factory=lambda: {"en-US": ""},
        description="URL for embedded video content.",
    )


# === Full Entry Object ===


class Entry(BaseModel):
    sys: EntrySys = Field(
        ..., description="System content type reference for Contentful."
    )
    fields: Fields = Field(..., description="Localized field values for the article.")


# === Upload Payload ===


class ContentfulArticlePayload(BaseModel):
    entries: List[Entry] = Field(
        ..., description="List of article entries for upload to Contentful."
    )
