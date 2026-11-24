# Fails the build of a target when the code generated from doomerfall_bridge.h is out of date.
set(DFB_BRIDGE_DIR "${CMAKE_CURRENT_LIST_DIR}")

function(dfb_require_fresh_bindings target)
	if(NOT TARGET doomerfall_bridge_bindings_check)
		find_package(Python3 REQUIRED COMPONENTS Interpreter)
		add_custom_target(doomerfall_bridge_bindings_check
			COMMAND "${Python3_EXECUTABLE}" "${DFB_BRIDGE_DIR}/generate_bindings.py" --check
			COMMENT "Checking generated bridge bindings"
			VERBATIM)
	endif()
	add_dependencies(${target} doomerfall_bridge_bindings_check)
endfunction()
