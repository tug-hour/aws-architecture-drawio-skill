"""Operational view gate: machine pass is necessary, not a visual sign-off."""
def display_quality(lay,display):
    width=lay['canvas']['width_pt'];height=lay['canvas']['height_pt'];scale=min(display['width_px']/width,display['height_px']/height)
    size=12*scale
    return {'status':'passed' if size>=display['min_text_px'] else 'needs-split','viewport':display,'text_px_at_fit':round(size,2),'scale_px_per_pt':round(scale,4),'diagram_size_pt':[width,height]}

def operational_quality(result,lay,display):
    warnings={w['code'] for w in result.get('warnings',[])}
    blocked=sorted(warnings & {'W_EDGE_CROSSINGS','W_EDGE_DETOUR','W_PORT_PROXIMITY','W_FRAME_WIRE_PROXIMITY','W_OVERLAY_INCLUDES_NONMEMBER','W_GROUP_SHARED_BORDER','W_EDGE_FRAME_TRANSIT','W_EDGE_CONTACT'})
    fit=display_quality(lay,display)
    return {'status':'passed' if result['status']=='passed' and not blocked and fit['status']=='passed' else 'needs-review-or-split','blocking_warnings':blocked,'display_quality':fit,'human_visual_review_required':True}
