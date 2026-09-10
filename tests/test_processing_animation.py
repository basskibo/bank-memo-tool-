from src.review.pipeline_messages import msg_extract_field, EXTRACT_FIELD_COUNT
from src.review.processing_animation import render_processing_animation_html


def test_lottie_box_cannot_expand_past_card():
    html = render_processing_animation_html(
        [msg_extract_field("revenue", 6, EXTRACT_FIELD_COUNT)],
        animation_id="proc-lottie-test",
    )
    assert "min-width: 132px" in html
    assert "max-width: 132px" in html
    assert "max-width: 100% !important" in html
    assert "preserveAspectRatio" in html
    assert ".processing-visual" in html
    assert "overflow: hidden" in html
