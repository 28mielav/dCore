#version 150
uniform sampler2D InSampler;
in vec2 texCoord;
out vec4 fragColor;
void main() {
    float mask = texture(InSampler, texCoord).a;
    fragColor = vec4(0.2, 0.8, 1.0, mask * 0.65);
}
