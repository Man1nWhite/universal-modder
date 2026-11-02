// nifly_wrap.cpp - a tiny C ABI around ousnius/nifly, so the Python tooling in
// this repo can cross-check its own NIF reader against the library that
// Outfit Studio / PyNifly use under the hood.
//
// Build (Linux, no cmake needed):
//   g++ -std=c++17 -O2 -fPIC -shared -I include -I external \
//       src/*.cpp nifly_wrap.cpp -o libniflywrap.so
//
// Everything is plain C at the boundary: no exceptions cross it, every getter
// writes into a caller-provided buffer and returns the number of elements, and
// the caller can ask for the required size first.

#include <cstring>
#include <string>
#include <vector>

#include "NifFile.hpp"
#include "Geometry.hpp"
#include "Shaders.hpp"
#include "Skin.hpp"
#include "Nodes.hpp"

using namespace nifly;

extern "C" {

struct NifWrap {
	NifFile* file = nullptr;
	std::vector<NiShape*> shapes;
	std::string error;
};

NifWrap* nifw_open(const char* path) {
	auto* wrap = new NifWrap();
	try {
		wrap->file = new NifFile();
		int result = wrap->file->Load(std::filesystem::path(path));
		if (result != 0) {
			wrap->error = "Load() returned " + std::to_string(result);
			return wrap;
		}
		wrap->shapes = wrap->file->GetShapes();
	}
	catch (const std::exception& e) {
		wrap->error = e.what();
	}
	return wrap;
}

void nifw_close(NifWrap* wrap) {
	if (!wrap)
		return;
	delete wrap->file;
	delete wrap;
}

const char* nifw_error(NifWrap* wrap) { return wrap ? wrap->error.c_str() : "null handle"; }

int nifw_shape_count(NifWrap* wrap) { return wrap ? static_cast<int>(wrap->shapes.size()) : 0; }

const char* nifw_shape_name(NifWrap* wrap, int index) {
	if (!wrap || index < 0 || index >= static_cast<int>(wrap->shapes.size()))
		return "";
	return wrap->shapes[index]->name.get().c_str();
}

int nifw_shape_num_vertices(NifWrap* wrap, int index) {
	if (!wrap || index < 0 || index >= static_cast<int>(wrap->shapes.size()))
		return 0;
	return wrap->shapes[index]->GetNumVertices();
}

int nifw_shape_num_triangles(NifWrap* wrap, int index) {
	if (!wrap || index < 0 || index >= static_cast<int>(wrap->shapes.size()))
		return 0;
	return static_cast<int>(wrap->shapes[index]->GetNumTriangles());
}

int nifw_shape_vertices(NifWrap* wrap, int index, float* out) {
	if (!wrap || index < 0 || index >= static_cast<int>(wrap->shapes.size()))
		return 0;
	NiShape* shape = wrap->shapes[index];
	std::vector<Vector3> legacy;
	if (auto* triShape = dynamic_cast<BSTriShape*>(shape)) {
		legacy = triShape->UpdateRawVertices();
	}
	else if (NiGeometryData* data = shape->GetGeomData()) {
		legacy = data->vertices;      // NiTriShape: vertices live in the data block
	}
	else {
		return 0;
	}
	auto& verts = legacy;
	for (size_t i = 0; i < verts.size(); i++) {
		out[i * 3 + 0] = verts[i].x;
		out[i * 3 + 1] = verts[i].y;
		out[i * 3 + 2] = verts[i].z;
	}
	return static_cast<int>(verts.size());
}

int nifw_shape_normals(NifWrap* wrap, int index, float* out) {
	if (!wrap || index < 0 || index >= static_cast<int>(wrap->shapes.size()))
		return 0;
	NiShape* shape = wrap->shapes[index];
	std::vector<Vector3> legacy;
	if (auto* triShape = dynamic_cast<BSTriShape*>(shape)) {
		legacy = triShape->UpdateRawNormals();
	}
	else if (NiGeometryData* data = shape->GetGeomData()) {
		legacy = data->normals;
	}
	else {
		return 0;
	}
	auto& norms = legacy;
	for (size_t i = 0; i < norms.size(); i++) {
		out[i * 3 + 0] = norms[i].x;
		out[i * 3 + 1] = norms[i].y;
		out[i * 3 + 2] = norms[i].z;
	}
	return static_cast<int>(norms.size());
}

int nifw_shape_uvs(NifWrap* wrap, int index, float* out) {
	if (!wrap || index < 0 || index >= static_cast<int>(wrap->shapes.size()))
		return 0;
	NiShape* shape = wrap->shapes[index];
	std::vector<Vector2> legacy;
	if (auto* triShape = dynamic_cast<BSTriShape*>(shape)) {
		legacy = triShape->UpdateRawUvs();
	}
	else if (NiGeometryData* data = shape->GetGeomData()) {
		if (data->uvSets.empty())
			return 0;
		legacy = data->uvSets[0];
	}
	else {
		return 0;
	}
	auto& uvs = legacy;
	for (size_t i = 0; i < uvs.size(); i++) {
		out[i * 2 + 0] = uvs[i].u;
		out[i * 2 + 1] = uvs[i].v;
	}
	return static_cast<int>(uvs.size());
}

int nifw_shape_triangles(NifWrap* wrap, int index, unsigned int* out) {
	if (!wrap || index < 0 || index >= static_cast<int>(wrap->shapes.size()))
		return 0;
	std::vector<Triangle> tris;
	if (!wrap->shapes[index]->GetTriangles(tris))
		return 0;
	for (size_t i = 0; i < tris.size(); i++) {
		out[i * 3 + 0] = tris[i].p1;
		out[i * 3 + 1] = tris[i].p2;
		out[i * 3 + 2] = tris[i].p3;
	}
	return static_cast<int>(tris.size());
}

int nifw_shape_has_uvs(NifWrap* wrap, int index) {
	if (!wrap || index < 0 || index >= static_cast<int>(wrap->shapes.size()))
		return 0;
	NiShape* shape = wrap->shapes[index];
	if (shape->HasUVs())
		return 1;
	if (NiGeometryData* data = shape->GetGeomData())
		return data->uvSets.empty() ? 0 : 1;
	return 0;
}

int nifw_shape_num_bones(NifWrap* wrap, int index) {
	if (!wrap || index < 0 || index >= static_cast<int>(wrap->shapes.size()))
		return 0;
	NiShape* shape = wrap->shapes[index];
	if (!shape->HasSkinInstance())
		return 0;
	auto* bones = wrap->file->GetHeader().GetBlock<NiBoneContainer>(*shape->SkinInstanceRef());
	if (!bones)
		return 0;
	return static_cast<int>(bones->boneRefs.GetSize());
}

const char* nifw_shape_bone_name(NifWrap* wrap, int index, int bone) {
	if (!wrap || index < 0 || index >= static_cast<int>(wrap->shapes.size()))
		return "";
	NiShape* shape = wrap->shapes[index];
	if (!shape->HasSkinInstance())
		return "";
	auto* bones = wrap->file->GetHeader().GetBlock<NiBoneContainer>(*shape->SkinInstanceRef());
	if (!bones || bone < 0 || bone >= static_cast<int>(bones->boneRefs.GetSize()))
		return "";
	auto* node = wrap->file->GetHeader().GetBlock<NiNode>(bones->boneRefs.GetBlockRef(bone));
	return node ? node->name.get().c_str() : "";
}

int nifw_shape_textures(NifWrap* wrap, int index, char* out, int out_size, int stride) {
	if (!wrap || index < 0 || index >= static_cast<int>(wrap->shapes.size()))
		return 0;
	NiShape* shape = wrap->shapes[index];
	if (!shape->HasShaderProperty())
		return 0;
	auto* shader = wrap->file->GetHeader().GetBlock<NiShader>(*shape->ShaderPropertyRef());
	if (!shader || !shader->HasTextureSet())
		return 0;
	auto* texSet = wrap->file->GetHeader().GetBlock<BSShaderTextureSet>(*shader->TextureSetRef());
	if (!texSet)
		return 0;
	int count = static_cast<int>(texSet->textures.size());
	if (count > 9)
		count = 9;
	for (int i = 0; i < count; i++) {
		std::string path = texSet->textures[i].get();
		if (stride > 0) {
			int len = static_cast<int>(path.size());
			if (len > stride - 1)
				len = stride - 1;
			std::memcpy(out + i * stride, path.data(), len);
			out[i * stride + len] = '\0';
		}
	}
	if (out_size > 0)
		out[0] = out[0];  // keep the parameter meaningful for static analysers
	return count;
}

int nifw_shape_shader_type(NifWrap* wrap, int index) {
	if (!wrap || index < 0 || index >= static_cast<int>(wrap->shapes.size()))
		return -1;
	NiShape* shape = wrap->shapes[index];
	if (!shape->HasShaderProperty())
		return -1;
	auto* shader = wrap->file->GetHeader().GetBlock<NiShader>(*shape->ShaderPropertyRef());
	return shader ? static_cast<int>(shader->GetShaderType()) : -1;
}

// Skinning: NiSkinData holds, per bone, the list of (vertex, weight) pairs.
int nifw_shape_num_weights(NifWrap* wrap, int index, int bone) {
	if (!wrap || index < 0 || index >= static_cast<int>(wrap->shapes.size()))
		return 0;
	NiShape* shape = wrap->shapes[index];
	if (!shape->HasSkinInstance())
		return 0;
	auto* skin = dynamic_cast<NiSkinInstance*>(
		wrap->file->GetHeader().GetBlock<NiBoneContainer>(*shape->SkinInstanceRef()));
	if (!skin)
		return 0;
	auto* data = wrap->file->GetHeader().GetBlock<NiSkinData>(skin->dataRef);
	if (!data || bone < 0 || bone >= static_cast<int>(data->bones.size()))
		return 0;
	return static_cast<int>(data->bones[bone].vertexWeights.size());
}

int nifw_shape_weights(NifWrap* wrap, int index, int bone, unsigned int* verts_out,
					   float* weights_out) {
	if (!wrap || index < 0 || index >= static_cast<int>(wrap->shapes.size()))
		return 0;
	NiShape* shape = wrap->shapes[index];
	if (!shape->HasSkinInstance())
		return 0;
	auto* skin = dynamic_cast<NiSkinInstance*>(
		wrap->file->GetHeader().GetBlock<NiBoneContainer>(*shape->SkinInstanceRef()));
	if (!skin)
		return 0;
	auto* data = wrap->file->GetHeader().GetBlock<NiSkinData>(skin->dataRef);
	if (!data || bone < 0 || bone >= static_cast<int>(data->bones.size()))
		return 0;
	const auto& weights = data->bones[bone].vertexWeights;
	for (size_t i = 0; i < weights.size(); i++) {
		verts_out[i] = weights[i].index;
		weights_out[i] = weights[i].weight;
	}
	return static_cast<int>(weights.size());
}

// Node tree, for comparing a decoded skeleton against another implementation.
int nifw_node_count(NifWrap* wrap) {
	if (!wrap || !wrap->file)
		return 0;
	return static_cast<int>(wrap->file->GetNodes().size());
}

const char* nifw_node_name(NifWrap* wrap, int index) {
	if (!wrap || !wrap->file)
		return "";
	auto nodes = wrap->file->GetNodes();
	if (index < 0 || index >= static_cast<int>(nodes.size()))
		return "";
	return nodes[index]->name.get().c_str();
}

int nifw_node_transform(NifWrap* wrap, int index, float* out) {
	// 10 floats: translation xyz, rotation 3x3 row-major, scale
	if (!wrap || !wrap->file)
		return 0;
	auto nodes = wrap->file->GetNodes();
	if (index < 0 || index >= static_cast<int>(nodes.size()))
		return 0;
	const MatTransform t = nodes[index]->GetTransformToParent();
	out[0] = t.translation.x;
	out[1] = t.translation.y;
	out[2] = t.translation.z;
	for (int r = 0; r < 3; r++)
		for (int c = 0; c < 3; c++)
			out[3 + r * 3 + c] = t.rotation[r][c];
	out[9] = t.scale;
	return 1;
}

int nifw_warnings(NifWrap* wrap, char* out, int stride, int max_count) {
	// nifly reports unreadable blocks through its IsValid()/unknown-block state;
	// surface the useful summary instead of silence.
	if (!wrap || !wrap->file || max_count < 1)
		return 0;
	std::string msg;
	if (!wrap->file->IsValid())
		msg = "nifly: file did not load";
	else if (wrap->file->HasUnknown())
		msg = "nifly: file contains unknown blocks";
	else
		msg = "nifly: loaded cleanly";
	int len = static_cast<int>(msg.size());
	if (len > stride - 1)
		len = stride - 1;
	std::memcpy(out, msg.data(), len);
	out[len] = '\0';
	return 1;
}

}  // extern "C"
