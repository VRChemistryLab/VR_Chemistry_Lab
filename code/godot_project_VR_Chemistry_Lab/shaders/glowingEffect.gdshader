shader_type spatial;
render_mode unshaded;

uniform vec4 glow_color : source_color = vec4(1.0, 0.8, 0.2, 1.0);
uniform float glow_strength = 5.0;
uniform float pulse_speed = 3.0;

void fragment()
{
    // unregelmäßiges Flackern statt perfektem Sinus
    float noise =
        sin(TIME * pulse_speed * 1.7) * 0.5 +
        sin(TIME * pulse_speed * 0.9) * 0.3 +
        sin(TIME * pulse_speed * 2.3) * 0.2;

    float pulse = smoothstep(0.2, 1.0, noise * 0.5 + 0.5);

    // nichtlineare Helligkeit (physikalischer)
    float heat = pow(pulse, 3.0);

    // Weißwerden bei hoher Intensität
    vec3 emissive_color = mix(
        glow_color.rgb,
        vec3(1.0),
        pow(pulse, 2.0)
    );

    // kleine „Hotspots“ für organische Struktur
    float hotspots =
        sin(UV.x * 40.0 + TIME * 2.0) *
        sin(UV.y * 40.0 + TIME * 1.7);

    hotspots = smoothstep(0.3, 1.0, hotspots * 0.5 + 0.5);

    EMISSION =
        emissive_color *
        glow_strength *
        heat *
        (0.7 + 0.3 * hotspots);
}