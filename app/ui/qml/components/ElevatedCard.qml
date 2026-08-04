import QtQuick

Item {
    id: root
    property alias radius: face.radius
    property alias color: face.color
    property bool elevated: Theme.productCardStyle !== "flat"
    property bool outlined: Theme.productCardStyle === "outlined"
    default property alias content: face.data

    transformOrigin: Item.Center

    Behavior on scale {
        NumberAnimation { duration: Math.max(80, Theme.animationMs / 2); easing.type: Easing.OutCubic }
    }

    Rectangle {
        visible: root.elevated && !root.outlined
        anchors.fill: face
        anchors.margins: -1
        anchors.topMargin: 4
        anchors.leftMargin: 2
        anchors.rightMargin: 2
        radius: face.radius + 2
        color: "#12000000"
        z: -2
    }
    Rectangle {
        visible: root.elevated && !root.outlined
        anchors.fill: face
        anchors.topMargin: 1
        radius: face.radius
        color: "#08000000"
        z: -1
    }

    Rectangle {
        id: face
        anchors.fill: parent
        radius: Theme.cornerRadius
        color: Theme.surface
        border.width: root.outlined || Theme.productCardStyle === "flat" ? 1 : 0
        border.color: "#E5E7EB"
        clip: true
    }
}
