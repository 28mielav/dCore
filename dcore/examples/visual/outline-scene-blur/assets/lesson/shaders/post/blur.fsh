#version 150
uniform sampler2D InSampler;
layout(std140) uniform BlurSettings { vec2 Direction; float Intensity; };
in vec2 texCoord;
out vec4 fragColor;
void main() {
    vec2 stepUV = Direction / vec2(textureSize(InSampler, 0));
    vec4 center = texture(InSampler, texCoord);
    vec4 sum = center * 0.4;
    sum += texture(InSampler, clamp(texCoord - stepUV, 0.0, 1.0)) * 0.2;
    sum += texture(InSampler, clamp(texCoord + stepUV, 0.0, 1.0)) * 0.2;
    sum += texture(InSampler, clamp(texCoord - 2.0 * stepUV, 0.0, 1.0)) * 0.1;
    sum += texture(InSampler, clamp(texCoord + 2.0 * stepUV, 0.0, 1.0)) * 0.1;
    fragColor = mix(center, sum, clamp(Intensity, 0.0, 1.0));
}
