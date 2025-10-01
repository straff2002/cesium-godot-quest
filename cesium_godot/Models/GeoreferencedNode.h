#ifndef GEOREFERENCED_NODE_H
#define GEOREFERENCED_NODE_H

#include "glm/ext/vector_double3.hpp"
#include "godot_cpp/classes/mesh_instance3d.hpp"
#include "godot_cpp/variant/vector3.hpp"
class CesiumGeoreference;

#if defined (CESIUM_GD_EXT)

using namespace godot;
#endif

class Cesium3DTileset;

// Not a fan of OOP, but, oh well

class GeoreferencedMesh : public MeshInstance3D {
	GDCLASS(GeoreferencedMesh, MeshInstance3D)

public:
	void _ready() override;
	
	void apply_position_on_globe(const glm::dvec3& engineOrigin);
	
	const glm::dvec3& get_original_position() const;
	
	/// @brief Intended to be used by C++ only
	void set_original_position(const glm::dvec3& position);

	/// @brief Intended to be used by GDScript only
	void set_engine_position(const Vector3& position);

	/// @brief Intended to be used by GDScript only
	void set_ecef_position(const Vector3& position);

	Vector3 get_ecef_position() const;
	
	Vector3 get_engine_position() const;

	void set_tileset(Cesium3DTileset* tileset);
	
	Cesium3DTileset* get_tileset() const;
	
	void set_tileset_no_reparent(Cesium3DTileset* tileset);
	
	CesiumGeoreference* get_georeference() const;
	
	// void set_ecef_position(const Vector3& position);


protected:
	glm::dvec3 m_originalPosition;

	Cesium3DTileset* m_tileset = nullptr;

	static void _bind_methods();
};

#endif
