cmake_minimum_required(VERSION 3.25)
project(PresenteriyakiWebViewKeys LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_AUTOMOC ON)
find_package(Qt6 6.12.0 EXACT REQUIRED COMPONENTS Core Gui Widgets WebViewPrivate)
set(plugin_source "${QT_SOURCE_DIR}/src/plugins/windows")
add_library(qtwebview_webview2 MODULE
    "${plugin_source}/qwebview2webview.cpp"
    "${plugin_source}/qwebview2webview_p.h"
    "${plugin_source}/qwebview2webviewplugin.cpp")
target_compile_definitions(qtwebview_webview2 PRIVATE QT_PLUGIN)
target_include_directories(qtwebview_webview2 PRIVATE "${WEBVIEW2_SDK_ROOT}/build/native/include")
target_link_libraries(qtwebview_webview2 PRIVATE Qt6::WebViewPrivate Qt6::Widgets urlmon
    "${WEBVIEW2_SDK_ROOT}/build/native/x64/WebView2LoaderStatic.lib")
set_target_properties(qtwebview_webview2 PROPERTIES PREFIX ""
    RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}/../plugins/webview")
