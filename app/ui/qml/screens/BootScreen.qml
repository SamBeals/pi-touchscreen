import QtQuick
import "../components"

Item {
    LoadingState {
        anchors.centerIn: parent
        width: parent.width
        message: App.bootMessage
    }
}
